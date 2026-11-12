"""Coletor incremental e alertas por e-mail, executado separadamente do web."""
from __future__ import annotations

import logging
import os
import re
import smtplib
import time
from datetime import date, timedelta
from email.message import EmailMessage
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .core import (
    AlertDelivery, Contract, SyncRun, SyncState,
    SessionLocal, TARGET_CNPJ, auto_classify_contract_units, init_db, upsert_contract,
    upsert_contract_term, upsert_procurement, utcnow, parse_int,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("contratos")
BASE = "https://pncp.gov.br/api/consulta/v1"
TERMS_BASE = "https://pncp.gov.br/api/pncp/v1"
COMPRAS_BASE = "https://dadosabertos.compras.gov.br"
EQUIPLANO_BASE = os.getenv("EQUIPLANO_BASE_URL", "https://turvopr.equiplano.com.br:7069").rstrip("/")
# shortcut: o portal público entrega cadeia TLS incompleta; reative a verificação quando o provedor corrigir o certificado.
EQUIPLANO_VERIFY_TLS = os.getenv("EQUIPLANO_VERIFY_TLS", "false").lower() == "true"
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
                    contract_processed = 0
                    try:
                        for item in contract_terms(client, contract):
                            result = upsert_contract_term(session, contract, item)
                            contract_processed += int(result in ("inserted", "updated"))
                        session.commit()
                        processed += contract_processed
                    except Exception:
                        errors += 1
                        session.rollback()
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


class _TableParser(HTMLParser):
    """Lê a tabela pública do Equiplano sem adicionar um parser HTML externo."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and (attrs.get("id") == "td" or (not self.in_table and not self.rows)):
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.row is not None and tag in {"td", "th"}:
            self.cell = {"text": [], "href": None}
        elif self.cell is not None and tag == "a":
            self.cell["href"] = attrs.get("href")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag):
        if self.row is not None and tag in {"td", "th"} and self.cell is not None:
            self.row.append({"text": " ".join("".join(self.cell["text"]).split()), "href": self.cell["href"]})
            self.cell = None
        elif self.in_table and tag == "tr" and self.row is not None:
            if self.row and any(cell["text"] or cell["href"] for cell in self.row):
                self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.in_table:
            self.in_table = False


def equiplano_table(body: str) -> list[list[dict]]:
    parser = _TableParser()
    parser.feed(body)
    empty_open = {"text": "", "href": None}
    return [[empty_open, *row] if len(row) == 10 else row for row in parser.rows]


def equiplano_date_range(value: str) -> tuple[date | None, date | None]:
    values = re.findall(r"\d{2}/\d{2}/\d{4}", value or "")
    parsed = []
    for item in values[:2]:
        try:
            parsed.append(date.fromisoformat(f"{item[6:]}-{item[3:5]}-{item[:2]}"))
        except ValueError:
            parsed.append(None)
    return (parsed + [None, None])[:2]


def equiplano_amount(value: str) -> str | None:
    value = re.sub(r"[^0-9,.-]", "", value or "")
    if not value:
        return None
    return value.replace(".", "").replace(",", ".")


def equiplano_object(value: str) -> str:
    value = str(value or "").strip()
    return "" if value in {".", "-", "—"} else value


def equiplano_query(year: int) -> str:
    params = {
        "formulario.codEntidade": "69",
        "formulario.exercicio": str(year),
        "formulario.tpAto": "CONTRATO",
        "formulario.isContratos": "true",
        "formulario.exercicioLicitacaoContrato": str(year),
        "formulario.tipoExercicioContrato": "0",
        "6578706f7274": "1",
        "d-5470-e": "9",
    }
    return urlencode(params)


def equiplano_supplier_index(client: httpx.Client, year: int) -> dict[tuple[int, str], dict]:
    index = {}
    supplier = ""
    start = 0
    while True:
        response = client.post(
            EQUIPLANO_BASE + "/transparencia/contratos/listaContratosAjax",
            data={
                "draw": "1", "start": str(start), "length": "500", "search[value]": "",
                "search[regex]": "false", "order[0][column]": "1", "order[0][dir]": "asc",
                "formulario.codEntidade": "69", "formulario.numeroContrato": "",
                "formulario.tipoExercicioContrato": "0", "formulario.exercicio": str(year),
                "formulario.codLicitacaoContrato": "", "formulario.exercicioLicitacaoContrato": str(year),
                "formulario.codTipoLicitacao": "", "formulario.nomeFornecedor": "",
                "formulario.sumulaContrato": "", "formulario.codPessoa": "",
                "formulario.nrDocumentoPessoa": "", "formulario.nmPessoa": "",
                "formulario.tipoResponsabilidade": "", "formulario.tpAto": "CONTRATO",
            },
        )
        if response.status_code == 204:
            break
        response.raise_for_status()
        body = response.json()
        pagination = body.get("paginacao") or {}
        rows = pagination.get("registrosAsJSONArray") or []
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if not isinstance(row, list):
                continue
            anchor = str(row[0] or "") if row else ""
            supplier_match = re.search(r"codFornecedor=(\d+)", anchor)
            if supplier_match and len(row) > 2:
                supplier = str(row[2] or "").strip()
                continue
            if len(row) < 5 or not row[2] or not supplier:
                continue
            match = re.search(r"Contrato\s+número\s+(.+)", str(row[2]), re.IGNORECASE)
            if match:
                number = match.group(1).strip()
                index[(year, number)] = {
                    "supplier": supplier,
                    "object": equiplano_object(row[4]),
                    "amount": str(row[3] or "").strip(),
                }
        total = pagination.get("recordsFiltered") or pagination.get("recordsTotal") or body.get("recordsFiltered") or body.get("recordsTotal")
        if total is not None and start + len(rows) >= int(total):
            break
        if total is None and len(rows) < 500:
            break
        start += len(rows)
        # shortcut: 100000 registros por ano, quando o provedor não informa total; aumentar com paginação confirmada.
        if start >= 100000:
            raise ValueError("Paginação excessiva no índice Equiplano; sincronização interrompida")
    return index


def equiplano_rows(client: httpx.Client, year: int) -> list[list[dict]]:
    response = client.get(EQUIPLANO_BASE + "/transparencia/contratos/listaContratosFornecedor?" + equiplano_query(year))
    response.raise_for_status()
    return equiplano_table(response.text)


def equiplano_payload(year: int, row: list[dict], supplier: dict) -> dict | None:
    if len(row) < 10:
        return None
    query = parse_qs(urlparse(row[0].get("href", "")).query)
    number = row[1].get("text", "").strip()
    contract_id = (query.get("formulario.idContrato") or [f"numero-{number}"])[0]
    if not number:
        return None
    start_date, end_date = equiplano_date_range(row[6].get("text", ""))
    key = f"equiplano:{year}:{contract_id}"
    return {
        "numeroControlePNCP": key,
        "orgaoEntidade": {"cnpj": TARGET_CNPJ},
        "numeroContratoEmpenho": number,
        "anoContrato": year,
        "sequencialContrato": None,
        "unidadeOrgao": {"nomeUnidade": "PREFEITURA MUNICIPAL DE TURVO - PR"},
        "nomeRazaoSocialFornecedor": supplier.get("supplier", ""),
        "objetoContrato": supplier.get("object", ""),
        "valorGlobal": equiplano_amount(row[9].get("text", "")),
        "dataVigenciaInicio": start_date.isoformat() if start_date else None,
        "dataVigenciaFim": end_date.isoformat() if end_date else None,
        "fonte": "Portal de Transparência / Equiplano",
        "fonteUrl": EQUIPLANO_BASE + "/transparencia/contratos",
        "equiplano": {"contract_id": contract_id, "row": row},
    }


def sync_equiplano():
    if os.getenv("EQUIPLANO_ENABLED", "true").lower() != "true":
        return
    start_year = int(os.getenv("EQUIPLANO_START_YEAR", os.getenv("SYNC_START_DATE", "2021-01-01")[:4]))
    with SessionLocal() as session:
        run = SyncRun(kind="equiplano")
        session.add(run)
        session.commit()
        processed = 0
        try:
            with httpx.Client(verify=EQUIPLANO_VERIFY_TLS, timeout=45, headers={"Accept": "text/html, application/json", "User-Agent": "ContratosTurvo/0.1"}) as client:
                for year in range(start_year, date.today().year + 1):
                    index = equiplano_supplier_index(client, year)
                    rows = equiplano_rows(client, year)
                    for row in rows:
                        if len(row) > 3 and row[3].get("text", "").casefold() == "contrato":
                            payload = equiplano_payload(year, row, index.get((year, row[1].get("text", "")), {}))
                            if payload:
                                result = upsert_contract(session, payload)
                                processed += int(result in ("inserted", "updated"))
                    session.commit()
                    for row in rows:
                        if len(row) < 4 or row[3].get("text", "").casefold() == "contrato":
                            continue
                        if len(row) < 10:
                            continue
                        query = parse_qs(urlparse(row[0].get("href", "")).query) if row and row[0].get("href") else {}
                        number = row[1].get("text", "").strip()
                        fallback_id = f"numero-{number}"
                        contract_id = (query.get("formulario.idContrato") or [fallback_id])[0]
                        parent = session.scalar(select(Contract).where(Contract.pncp_key == f"equiplano:{year}:{contract_id}"))
                        if not parent:
                            continue
                        sequence = parse_int(row[2].get("text"))
                        if sequence is None:
                            continue
                        start_date, end_date = equiplano_date_range(row[6].get("text", ""))
                        term_type_name = row[3].get("text", "") + (" / " + row[5].get("text", "") if row[5].get("text") else "")
                        normalized_term_type = term_type_name.casefold()
                        term = {
                            "sequencialTermoContrato": sequence,
                            "numeroTermoContrato": row[2].get("text", ""),
                            "tipoTermoContrato": {"nome": term_type_name},
                            "objetoTermoContrato": parent.object,
                            "dataVigenciaInicio": start_date.isoformat() if start_date else None,
                            "dataVigenciaFim": end_date.isoformat() if end_date else None,
                            "valorGlobal": equiplano_amount(row[9].get("text", "")),
                            "qualificacaoAcrescimoSupressao": "valor" in normalized_term_type,
                            "qualificacaoVigencia": "prazo" in normalized_term_type,
                            "excluido": "anula" in normalized_term_type,
                            "fonte": "Portal de Transparência / Equiplano",
                            "fonteUrl": EQUIPLANO_BASE + "/transparencia/contratos",
                            "equiplano": {"row": row},
                        }
                        result = upsert_contract_term(session, parent, term)
                        processed += int(result in ("inserted", "updated"))
                    session.commit()
            auto_classify_contract_units(session)
            run.processed = processed
            run.status = "ok"
            run.finished_at = utcnow()
            session.commit()
            LOG.info("equiplano: %d alterações", processed)
        except Exception as exc:
            session.rollback()
            run.status = "error"
            run.finished_at = utcnow()
            run.error = str(exc)[:800]
            session.commit()
            LOG.exception("Falha Equiplano")


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
        for attempt in range(4):
            try:
                response = client.get(COMPRAS_BASE + "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133", params=query)
                if response.status_code == 204:
                    return
                if response.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError("Compras.gov temporariamente indisponível", request=response.request, response=response)
                response.raise_for_status()
                body = response.json()
                break
            except (httpx.HTTPError, ValueError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        if not isinstance(body, dict):
            raise ValueError("Resposta inesperada do Compras.gov: objeto esperado")
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
            sync_equiplano()
            sync_procurements()
            alerts()
        except Exception:
            LOG.exception("Falha no ciclo do coletor")
        time.sleep(max(300, int(os.getenv("WORKER_INTERVAL_SECONDS", "3600"))))


if __name__ == "__main__":
    main()
