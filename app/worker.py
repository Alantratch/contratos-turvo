"""Coletor incremental e alertas por e-mail, executado separadamente do web."""
from __future__ import annotations

import logging
import os
import smtplib
import time
from datetime import date, timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .core import (
    AlertDelivery, Contract, SyncRun, SyncState,
    SessionLocal, TARGET_CNPJ, auto_classify_contract_units, init_db, upsert_contract,
    upsert_contract_term, upsert_procurement, utcnow,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("contratos")
BASE = "https://pncp.gov.br/api/consulta/v1"
TERMS_BASE = "https://pncp.gov.br/api/pncp/v1"
COMPRAS_BASE = "https://dadosabertos.compras.gov.br"
PAGE_SIZE = 100


def pages(client: httpx.Client, endpoint: str, begin: date, end: date):
    page = 1
    while True:
        query = {
            "dataInicial": begin.strftime("%Y%m%d"), "dataFinal": end.strftime("%Y%m%d"),
            "cnpjOrgao": TARGET_CNPJ, "pagina": page, "tamanhoPagina": PAGE_SIZE,
        }
        for attempt in range(4):
            try:
                response = client.get(BASE + endpoint, params=query)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError("PNCP temporariamente indisponível", request=response.request, response=response)
                if response.status_code == 204:
                    return
                response.raise_for_status()
                body = response.json()
                break
            except (httpx.HTTPError, ValueError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        items = body.get("data") or []
        if not isinstance(items, list):
            raise ValueError("Resposta inesperada do PNCP: data não é lista")
        yield items
        total_pages = int(body.get("totalPaginas") or 1)
        if page >= total_pages:
            break
        if page >= 10000:
            raise ValueError("Paginação excessiva; sincronização interrompida")
        page += 1


def sync_window(endpoint: str, start: date, end: date, kind: str):
    with SessionLocal() as session:
        run = SyncRun(kind=kind)
        session.add(run)
        session.commit()
        try:
            processed = 0
            with httpx.Client(timeout=25, headers={"Accept": "application/json", "User-Agent": "ContratosTurvo/0.1"}) as client:
                for batch in pages(client, endpoint, start, end):
                    for item in batch:
                        result = upsert_contract(session, item)
                        processed += int(result in ("inserted", "updated"))
                    auto_classify_contract_units(session)
                    session.commit()
            run.processed = processed
            run.status = "ok"
            run.finished_at = utcnow()
            session.commit()
            LOG.info("%s %s..%s: %d alterações", kind, start, end, processed)
            return True
        except Exception as exc:
            session.rollback()
            run.status = "error"
            run.finished_at = utcnow()
            run.error = str(exc)[:800]
            session.commit()
            LOG.exception("Falha PNCP em %s %s..%s", kind, start, end)
            return False


def sync_publication():
    today = date.today()
    with SessionLocal() as session:
        state = session.get(SyncState, "publication")
        if not state:
            state = SyncState(name="publication", next_day=date.fromisoformat(os.getenv("SYNC_START_DATE", "2021-01-01")))
            session.add(state)
            session.commit()
        next_day = state.next_day
    windows = max(1, min(30, int(os.getenv("PUBLICATION_WINDOWS_PER_CYCLE", "6"))))
    for _ in range(windows):
        if next_day > today:
            break
        end = min(next_day + timedelta(days=29), today)
        if not sync_window("/contratos", next_day, end, "publication"):
            break
        next_day = end + timedelta(days=1)
        with SessionLocal() as session:
            state = session.get(SyncState, "publication")
            state.next_day = next_day
            session.commit()


def sync_updates():
    today = date.today()
    # Releitura de publicação cobre atrasos; atualização global busca mudanças em registros antigos.
    start = today - timedelta(days=14)
    sync_window("/contratos/atualizacao", start, today, "updates")
    sync_window("/contratos", today - timedelta(days=7), today, "recent-publication")


def contract_terms(client: httpx.Client, contract: Contract) -> list[dict]:
    if contract.year is None or contract.sequence is None:
        return []
    url = f"{TERMS_BASE}/orgaos/{TARGET_CNPJ}/contratos/{contract.year}/{contract.sequence}/termos"
    for attempt in range(3):
        try:
            response = client.get(url)
            if response.status_code in (204, 400, 404):
                return []
            if response.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError("PNCP de termos temporariamente indisponível", request=response.request, response=response)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, list):
                raise ValueError("Resposta inesperada do PNCP: termos não são uma lista")
            return body
        except (httpx.HTTPError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return []


def sync_terms():
    """Atualiza termos de todos os contratos, inclusive aditivos publicados depois do contrato."""
    with SessionLocal() as session:
        run = SyncRun(kind="terms")
        session.add(run)
        session.commit()
        processed = 0
        errors = 0
        try:
            contracts = session.scalars(select(Contract).order_by(Contract.id)).all()
            with httpx.Client(timeout=15, headers={"Accept": "application/json", "User-Agent": "ContratosTurvo/0.1"}) as client:
                for contract in contracts:
                    try:
                        for item in contract_terms(client, contract):
                            result = upsert_contract_term(session, contract, item)
                            processed += int(result in ("inserted", "updated"))
                        if contract.id % 25 == 0:
                            session.commit()
                    except Exception:
                        errors += 1
                        LOG.exception("Falha ao consultar termos do contrato %s", contract.pncp_key)
            run.processed = processed
            run.status = "error" if errors else "ok"
            run.error = f"{errors} contrato(s) não consultado(s)" if errors else None
            run.finished_at = utcnow()
            session.commit()
            LOG.info("termos: %d alterações, %d falhas", processed, errors)
        except Exception as exc:
            session.rollback()
            run.status = "error"
            run.finished_at = utcnow()
            run.error = str(exc)[:800]
            session.commit()
            LOG.exception("Falha na sincronização de termos")


def classify_existing_contracts():
    with SessionLocal() as session:
        changed = auto_classify_contract_units(session)
        session.commit()
        if changed:
            LOG.info("classificação automática por unidade: %d contratos", changed)


def compras_pages(client: httpx.Client, modality: int, begin: date, end: date):
    page = 1
    while True:
        query = {
            "dataPublicacaoPncpInicial": begin.isoformat(),
            "dataPublicacaoPncpFinal": end.isoformat(),
            "orgaoEntidadeCnpj": TARGET_CNPJ,
            "codigoModalidade": modality,
            "pagina": page,
            "tamanhoPagina": 500,
        }
        response = client.get(COMPRAS_BASE + "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133", params=query)
        if response.status_code == 400:
            return
        response.raise_for_status()
        body = response.json()
        items = body.get("resultado") or []
        if not isinstance(items, list):
            raise ValueError("Resposta inesperada do Compras.gov: resultado não é lista")
        if items:
            yield items
        total_pages = int(body.get("totalPaginas") or 1)
        if page >= total_pages:
            break
        if page >= 10000:
            raise ValueError("Paginação excessiva no Compras.gov; sincronização interrompida")
        page += 1


def sync_procurements():
    today = date.today()
    start = date(today.year, 1, 1)
    with SessionLocal() as session:
        run = SyncRun(kind="compras-gov")
        session.add(run)
        session.commit()
        try:
            processed = 0
            with httpx.Client(timeout=25, headers={"Accept": "application/json", "User-Agent": "ContratosTurvo/0.1"}) as client:
                for modality in range(1, 15):
                    for batch in compras_pages(client, modality, start, today):
                        for item in batch:
                            result = upsert_procurement(session, item)
                            processed += int(result in ("inserted", "updated"))
                        session.commit()
            run.processed = processed
            run.status = "ok"
            run.finished_at = utcnow()
            session.commit()
            LOG.info("compras-gov %s..%s: %d alterações", start, today, processed)
        except Exception as exc:
            session.rollback()
            run.status = "error"
            run.finished_at = utcnow()
            run.error = str(exc)[:800]
            session.commit()
            LOG.exception("Falha Compras.gov %s..%s", start, today)


def alert_threshold(days: int) -> int | None:
    if days < 0 or days > 120:
        return None
    for threshold in (0, 7, 15, 30, 60, 90, 120):
        if days <= threshold:
            return threshold
    return None


def send_email(to: str, subject: str, body: str):
    host = os.getenv("SMTP_HOST", "")
    sender = os.getenv("SMTP_FROM", "")
    if not host or not sender:
        raise RuntimeError("SMTP_HOST e SMTP_FROM são necessários")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message)


def alerts():
    if os.getenv("ALERTS_ENABLED", "false").lower() != "true":
        LOG.info("Envio de alertas desativado até homologação")
        return
    today = date.today()
    with SessionLocal() as session:
        candidates = session.scalars(
            select(Contract).options(joinedload(Contract.secretary))
            .where(Contract.end_date.between(today, today + timedelta(days=120)))
        ).all()
        for contract in candidates:
            if not contract.secretary or not contract.secretary.email:
                continue
            days = (contract.end_date - today).days
            threshold = alert_threshold(days)
            if threshold is None:
                continue
            recipient = contract.secretary.email
            exists = session.scalar(select(AlertDelivery).where(
                AlertDelivery.contract_id == contract.id,
                AlertDelivery.threshold_days == threshold,
                AlertDelivery.due_date == contract.end_date,
                AlertDelivery.recipient == recipient,
            ))
            if exists:
                continue
            try:
                send_email(
                    recipient,
                    "Atenção: contrato %s vence em %s dias" % (contract.number, days),
                    ("Prefeitura de Turvo/PR\nContrato: %s\nSecretaria: %s\nFornecedor: %s\n"
                     "Vigência cadastrada no PNCP até: %s\nFaltam: %s dias\n\n"
                     "Verificar aditivos, situação jurídica e providências com o setor de contratos.")
                    % (contract.number, contract.secretary.name, contract.supplier, contract.end_date.isoformat(), days),
                )
                session.add(AlertDelivery(contract_id=contract.id, threshold_days=threshold,
                                          due_date=contract.end_date, recipient=recipient))
                session.commit()
            except Exception:
                session.rollback()
                LOG.exception("Erro ao enviar alerta para contrato %s", contract.id)


def main():
    init_db()
    while True:
        try:
            sync_publication()
            sync_updates()
            classify_existing_contracts()
            sync_terms()
            sync_procurements()
            alerts()
        except Exception:
            LOG.exception("Falha no ciclo do coletor")
        time.sleep(max(300, int(os.getenv("WORKER_INTERVAL_SECONDS", "3600"))))


if __name__ == "__main__":
    main()
