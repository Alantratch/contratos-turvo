"""Persistência e normalização de dados do PNCP."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL é obrigatório; não inicie sem banco configurado.")

TARGET_CNPJ = re.sub(r"\D", "", os.getenv("TARGET_CNPJ", "78279973000107"))
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Secretary(Base):
    __tablename__ = "secretaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(250))


class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    pncp_key: Mapped[str] = mapped_column(String(110), unique=True, index=True)
    buyer_cnpj: Mapped[str] = mapped_column(String(14), index=True)
    number: Mapped[str] = mapped_column(String(70), default="")
    year: Mapped[int | None] = mapped_column(Integer)
    sequence: Mapped[int | None] = mapped_column(Integer)
    supplier: Mapped[str] = mapped_column(String(300), default="")
    object: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(String(250), default="")
    unit_code: Mapped[str] = mapped_column(String(100), default="")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    start_date: Mapped[date | None] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, index=True)
    procurement_key: Mapped[str | None] = mapped_column(String(110), index=True)
    secretary_id: Mapped[int | None] = mapped_column(ForeignKey("secretaries.id"), index=True)
    secretary: Mapped[Secretary | None] = relationship()
    digest: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    terms: Mapped[list["ContractTerm"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", lazy="selectin",
        order_by="ContractTerm.sequence",
    )


class ContractTerm(Base):
    """Termo contratual publicado pelo PNCP, incluindo aditivo e apostilamento."""
    __tablename__ = "contract_terms"
    id: Mapped[int] = mapped_column(primary_key=True)
    term_key: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    number: Mapped[str] = mapped_column(String(70), default="")
    type_id: Mapped[int | None] = mapped_column(Integer)
    type_name: Mapped[str] = mapped_column(String(120), default="")
    object: Mapped[str] = mapped_column(Text, default="")
    signed_date: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    published_at: Mapped[date | None] = mapped_column(Date)
    amount_added: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    global_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    deadline_days: Mapped[int | None] = mapped_column(Integer)
    qualifies_amount: Mapped[bool] = mapped_column(Boolean, default=False)
    qualifies_duration: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    digest: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict] = mapped_column(JSON)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    contract: Mapped[Contract] = relationship(back_populates="terms")


class Procurement(Base):
    """Contratação publicada no Compras.gov; não é confundida com contrato assinado."""
    __tablename__ = "procurements"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(110), unique=True, index=True)
    buyer_cnpj: Mapped[str] = mapped_column(String(14), index=True)
    number: Mapped[str] = mapped_column(String(70), default="")
    year: Mapped[int | None] = mapped_column(Integer)
    sequence: Mapped[int | None] = mapped_column(Integer)
    modality: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(120), default="")
    object: Mapped[str] = mapped_column(Text, default="")
    process: Mapped[str] = mapped_column(String(120), default="")
    estimated_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    awarded_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    opening_date: Mapped[date | None] = mapped_column(Date, index=True)
    published_at: Mapped[date | None] = mapped_column(Date, index=True)
    proposal_end: Mapped[date | None] = mapped_column(Date)
    result_exists: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    info_url: Mapped[str | None] = mapped_column(String(600))
    digest: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict] = mapped_column(JSON)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContractRevision(Base):
    __tablename__ = "contract_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    digest: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncState(Base):
    __tablename__ = "sync_state"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    next_day: Mapped[date] = mapped_column(Date)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    processed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    threshold_days: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    recipient: Mapped[str] = mapped_column(String(250))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON)


def init_db() -> None:
    Base.metadata.create_all(engine)
    additions = {
        "contracts": {"procurement_key": "VARCHAR(110)"},
        "procurements": {
            "opening_date": "DATE",
            "result_exists": "BOOLEAN DEFAULT FALSE",
            "info_url": "VARCHAR(600)",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_contracts_procurement_key ON contracts (procurement_key)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_procurements_opening_date ON procurements (opening_date)"))
    changed = False
    with SessionLocal() as session:
        for contract in session.scalars(select(Contract).where(Contract.procurement_key.is_(None))).all():
            key = (contract.raw or {}).get("numeroControlePncpCompra") if isinstance(contract.raw, dict) else None
            if key:
                contract.procurement_key = str(key)[:110]
                changed = True
        for procurement in session.scalars(select(Procurement)).all():
            raw = procurement.raw if isinstance(procurement.raw, dict) else {}
            if procurement.opening_date is None and raw.get("dataAberturaPropostaPncp"):
                procurement.opening_date = parse_date(raw.get("dataAberturaPropostaPncp"))
                changed = True
            if not procurement.result_exists and "existeResultado" in raw:
                procurement.result_exists = bool(raw.get("existeResultado"))
                changed = True
            if procurement.info_url is None and raw.get("informacaoComplementar"):
                procurement.info_url = extract_url(raw.get("informacaoComplementar"))
                changed = True
        if changed:
            session.commit()


def parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def extract_url(value: str | None) -> str | None:
    match = re.search(r"https?://[^\s<>\"]+", str(value or ""))
    return match.group(0).rstrip(".,;)") if match else None


def parse_amount(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def upsert_contract(session: Session, payload: dict) -> str:
    """Importa somente o CNPJ-alvo. Preserva secretaria e snapshots em alterações."""
    if not isinstance(payload, dict):
        return "ignored"
    organization = payload.get("orgaoEntidade") or {}
    buyer = re.sub(r"\D", "", str(organization.get("cnpj") or payload.get("cnpjOrgao") or ""))
    key = str(payload.get("numeroControlePNCP") or "").strip()
    if buyer != TARGET_CNPJ or not key:
        return "ignored"

    raw = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    current = session.scalar(select(Contract).where(Contract.pncp_key == key))
    if current and current.digest == digest:
        current.last_seen_at = utcnow()
        return "unchanged"

    unit = raw.get("unidadeOrgao") or {}
    fields = {
        "buyer_cnpj": buyer,
        "number": str(raw.get("numeroContratoEmpenho") or "")[:70],
        "year": raw.get("anoContrato"),
        "sequence": raw.get("sequencialContrato"),
        "supplier": str(raw.get("nomeRazaoSocialFornecedor") or "")[:300],
        "object": str(raw.get("objetoContrato") or raw.get("objeto") or ""),
        "unit": str(unit.get("nomeUnidade") or "")[:250],
        "unit_code": str(unit.get("codigoUnidade") or "")[:100],
        "amount": parse_amount(raw.get("valorGlobal")),
        "start_date": parse_date(raw.get("dataVigenciaInicio")),
        "end_date": parse_date(raw.get("dataVigenciaFim")),
        "procurement_key": str(raw.get("numeroControlePncpCompra") or "")[:110] or None,
        "digest": digest,
        "raw": raw,
        "last_seen_at": utcnow(),
    }
    status = "updated" if current else "inserted"
    if current is None:
        current = Contract(pncp_key=key, **fields)
        session.add(current)
    else:
        for column, value in fields.items():
            setattr(current, column, value)
    session.flush()
    session.add(ContractRevision(contract_id=current.id, digest=digest, raw=raw))
    return status


def refresh_contract_effective_fields(contract: Contract) -> None:
    """Aplica ao contrato a última vigência/valor publicado em termos ativos."""
    terms = [term for term in contract.terms if not term.excluded]
    if not terms:
        return
    latest = max(terms, key=lambda term: (term.sequence, term.published_at or date.min))
    if latest.start_date:
        contract.start_date = latest.start_date
    if latest.end_date:
        contract.end_date = latest.end_date
    if latest.global_amount is not None and latest.qualifies_amount:
        contract.amount = latest.global_amount


def upsert_contract_term(session: Session, contract: Contract, payload: dict) -> str:
    """Importa um termo do PNCP e mantém a vigência efetiva do contrato."""
    if not isinstance(payload, dict):
        return "ignored"
    sequence = parse_int(payload.get("sequencialTermoContrato"))
    if sequence is None:
        return "ignored"
    raw = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    key = f"{contract.pncp_key}#termo-{sequence}"
    current = session.scalar(select(ContractTerm).where(ContractTerm.term_key == key))
    if current and current.digest == digest:
        current.last_seen_at = utcnow()
        return "unchanged"
    term_type = raw.get("tipoTermoContrato") or {}
    fields = {
        "contract_id": contract.id,
        "sequence": sequence,
        "number": str(raw.get("numeroTermoContrato") or "")[:70],
        "type_id": parse_int(term_type.get("id") if isinstance(term_type, dict) else raw.get("tipoTermoContratoId")),
        "type_name": str(term_type.get("nome") if isinstance(term_type, dict) else "")[:120],
        "object": str(raw.get("objetoTermoContrato") or ""),
        "signed_date": parse_date(raw.get("dataAssinatura")),
        "start_date": parse_date(raw.get("dataVigenciaInicio")),
        "end_date": parse_date(raw.get("dataVigenciaFim")),
        "published_at": parse_date(raw.get("dataPublicacaoPncp")),
        "amount_added": parse_amount(raw.get("valorAcrescido")),
        "global_amount": parse_amount(raw.get("valorGlobal")),
        "deadline_days": parse_int(raw.get("prazoAditadoDias")),
        "qualifies_amount": bool(raw.get("qualificacaoAcrescimoSupressao")),
        "qualifies_duration": bool(raw.get("qualificacaoVigencia")),
        "excluded": bool(raw.get("excluido")),
        "digest": digest,
        "raw": raw,
        "last_seen_at": utcnow(),
    }
    status = "updated" if current else "inserted"
    if current is None:
        current = ContractTerm(term_key=key, **fields)
        session.add(current)
    else:
        for column, value in fields.items():
            setattr(current, column, value)
    session.flush()
    if current not in contract.terms:
        contract.terms.append(current)
    refresh_contract_effective_fields(contract)
    return status


def upsert_procurement(session: Session, payload: dict) -> str:
    """Importa contratações do Compras.gov sem apresentá-las como contratos."""
    if not isinstance(payload, dict):
        return "ignored"
    buyer = re.sub(r"\D", "", str(payload.get("orgaoEntidadeCnpj") or ""))
    key = str(payload.get("numeroControlePNCP") or "").strip()
    if buyer != TARGET_CNPJ or not key:
        return "ignored"
    raw = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    current = session.scalar(select(Procurement).where(Procurement.source_key == key))
    if current and current.digest == digest:
        current.last_seen_at = utcnow()
        return "unchanged"
    fields = {
        "buyer_cnpj": buyer,
        "number": str(raw.get("numeroCompra") or "")[:70],
        "year": raw.get("anoCompraPncp"),
        "sequence": raw.get("sequencialCompraPncp"),
        "modality": str(raw.get("modalidadeNome") or "")[:120],
        "status": str(raw.get("situacaoCompraNomePncp") or "")[:120],
        "object": str(raw.get("objetoCompra") or ""),
        "process": str(raw.get("processo") or "")[:120],
        "estimated_amount": parse_amount(raw.get("valorTotalEstimado")),
        "awarded_amount": parse_amount(raw.get("valorTotalHomologado")),
        "opening_date": parse_date(raw.get("dataAberturaPropostaPncp")),
        "published_at": parse_date(raw.get("dataPublicacaoPncp")),
        "proposal_end": parse_date(raw.get("dataEncerramentoPropostaPncp")),
        "result_exists": bool(raw.get("existeResultado")),
        "info_url": extract_url(raw.get("informacaoComplementar")),
        "digest": digest,
        "raw": raw,
        "last_seen_at": utcnow(),
    }
    status = "updated" if current else "inserted"
    if current is None:
        session.add(Procurement(source_key=key, **fields))
    else:
        for column, value in fields.items():
            setattr(current, column, value)
    return status


def auto_classify_contract_units(session: Session) -> int:
    """Cria áreas a partir da unidade oficial e não tenta adivinhar gestor ou e-mail."""
    generic_units = {"PREFEITURA MUNICIPAL DE TURVO - PR"}
    areas = {row.name: row for row in session.scalars(select(Secretary)).all()}
    changed = 0
    contracts = session.scalars(select(Contract).where(Contract.secretary_id.is_(None), Contract.unit != "")).all()
    for contract in contracts:
        name = contract.unit.strip()
        if not name or name in generic_units:
            continue
        area = areas.get(name)
        if area is None:
            area = Secretary(name=name[:160])
            session.add(area)
            session.flush()
            areas[name] = area
        contract.secretary_id = area.id
        changed += 1
    return changed


def serialize_contract(c: Contract) -> dict:
    terms = [serialize_contract_term(term) for term in c.terms if not term.excluded]
    return {
        "id": c.id, "pncp_key": c.pncp_key, "number": c.number,
        "year": c.year, "sequence": c.sequence, "buyer_cnpj": c.buyer_cnpj,
        "supplier": c.supplier, "object": c.object, "unit": c.unit,
        "amount": str(c.amount) if c.amount is not None else None,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "secretary_id": c.secretary_id,
        "secretary": c.secretary.name if c.secretary else None,
        "terms_count": len(terms),
        "terms": terms,
    }


def serialize_contract_term(term: ContractTerm) -> dict:
    return {
        "id": term.id,
        "contract_id": term.contract_id,
        "kind": "termo",
        "sequence": term.sequence,
        "number": term.number,
        "type_name": term.type_name or "Termo contratual",
        "object": term.object,
        "signed_date": term.signed_date.isoformat() if term.signed_date else None,
        "start_date": term.start_date.isoformat() if term.start_date else None,
        "end_date": term.end_date.isoformat() if term.end_date else None,
        "published_at": term.published_at.isoformat() if term.published_at else None,
        "amount_added": str(term.amount_added) if term.amount_added is not None else None,
        "global_amount": str(term.global_amount) if term.global_amount is not None else None,
        "deadline_days": term.deadline_days,
        "qualifies_amount": term.qualifies_amount,
        "qualifies_duration": term.qualifies_duration,
    }


def procurement_phase(p: Procurement, contracts: list[Contract] | None = None, today: date | None = None) -> dict[str, str]:
    today = today or date.today()
    source_status = (p.status or "").casefold()
    if "anulad" in source_status:
        return {"key": "cancelled", "label": "Anulada"}
    if "revogad" in source_status:
        return {"key": "revoked", "label": "Revogada"}
    if "suspens" in source_status:
        return {"key": "suspended", "label": "Suspensa"}
    if p.result_exists or p.awarded_amount is not None:
        return {"key": "result", "label": "Resultado publicado"}
    if p.opening_date and p.opening_date > today:
        return {"key": "scheduled", "label": "Sessão agendada"}
    if p.opening_date and p.opening_date == today:
        return {"key": "today", "label": "Sessão hoje"}
    if p.proposal_end and p.proposal_end >= today:
        return {"key": "in_progress", "label": "Em andamento"}
    if contracts:
        return {"key": "contracted", "label": "Contrato publicado"}
    return {"key": "pending", "label": "Aguardando resultado"}


def serialize_procurement(p: Procurement, contracts: list[Contract] | None = None) -> dict:
    contracts = contracts or []
    phase = procurement_phase(p, contracts)
    linked_contracts = [{
        "id": contract.id,
        "number": contract.number,
        "year": contract.year,
        "supplier": contract.supplier,
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "pncp_key": contract.pncp_key,
    } for contract in (contracts or [])]
    result_labels = {
        "scheduled": "Ainda não ocorreu",
        "today": "Sessão hoje",
        "in_progress": "Em andamento",
        "pending": "Aguardando publicação do resultado",
        "result": "Resultado publicado",
        "contracted": "Contrato publicado",
        "cancelled": "Não se aplica · anulada",
        "revoked": "Não se aplica · revogada",
        "suspended": "Aguardando decisão · suspensa",
    }
    info_status = "Consultar quadro informativo oficial" if p.info_url else "Não informado pela fonte"
    return {
        "id": p.id, "source_key": p.source_key, "number": p.number,
        "year": p.year, "sequence": p.sequence, "buyer_cnpj": p.buyer_cnpj,
        "modality": p.modality, "status": p.status, "object": p.object,
        "process": p.process,
        "estimated_amount": str(p.estimated_amount) if p.estimated_amount is not None else None,
        "awarded_amount": str(p.awarded_amount) if p.awarded_amount is not None else None,
        "opening_date": p.opening_date.isoformat() if p.opening_date else None,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "proposal_end": p.proposal_end.isoformat() if p.proposal_end else None,
        "result_exists": p.result_exists,
        "result_label": result_labels[phase["key"]],
        "phase": phase["key"],
        "phase_label": phase["label"],
        "impugnation_status": info_status,
        "impugnation_url": p.info_url,
        "contracts": linked_contracts,
        "contract_status": "Contrato publicado" if linked_contracts else "Nenhum contrato PNCP vinculado",
    }
