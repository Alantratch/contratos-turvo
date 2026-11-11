"""Persistência e normalização de dados do PNCP."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, create_engine, select
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
    secretary_id: Mapped[int | None] = mapped_column(ForeignKey("secretaries.id"), index=True)
    secretary: Mapped[Secretary | None] = relationship()
    digest: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
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


def parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def parse_amount(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
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
        "object": str(raw.get("objetoContrato") or ""),
        "unit": str(unit.get("nomeUnidade") or "")[:250],
        "unit_code": str(unit.get("codigoUnidade") or "")[:100],
        "amount": parse_amount(raw.get("valorGlobal")),
        "start_date": parse_date(raw.get("dataVigenciaInicio")),
        "end_date": parse_date(raw.get("dataVigenciaFim")),
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


def serialize_contract(c: Contract) -> dict:
    return {
        "id": c.id, "pncp_key": c.pncp_key, "number": c.number,
        "year": c.year, "sequence": c.sequence, "buyer_cnpj": c.buyer_cnpj,
        "supplier": c.supplier, "object": c.object, "unit": c.unit,
        "amount": str(c.amount) if c.amount is not None else None,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "secretary_id": c.secretary_id,
        "secretary": c.secretary.name if c.secretary else None,
    }
