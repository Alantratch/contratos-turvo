"""API e interface de gestão de contratos (uso interno)."""
from __future__ import annotations

import base64
import hmac
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from .core import (
    AuditEvent, Contract, Procurement, Secretary, SyncRun, SyncState,
    SessionLocal, init_db, serialize_contract, serialize_procurement
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Contratos Turvo", docs_url=None, redoc_url=None, lifespan=lifespan)
STATIC = Path(__file__).with_name("static")


@app.middleware("http")
async def require_auth(request: Request, call_next):
    if request.url.path == "/healthz":
        return await call_next(request)
    username = os.getenv("DASHBOARD_USERNAME")
    password = os.getenv("DASHBOARD_PASSWORD")
    if not username or not password:
        return JSONResponse({"detail": "Credenciais não configuradas"}, status_code=503)
    try:
        scheme, token = request.headers.get("authorization", "").split(" ", 1)
        if scheme.lower() != "basic":
            raise ValueError("Esquema inválido")
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
        supplied_user, supplied_password = decoded.split(":", 1)
        if not (hmac.compare_digest(supplied_user, username) and hmac.compare_digest(supplied_password, password)):
            raise ValueError("Credenciais inválidas")
    except (ValueError, UnicodeError):
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Contratos Turvo"'})

    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc.lower() != request.headers.get("host", "").lower():
            return JSONResponse({"detail": "Origem não autorizada"}, status_code=403)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "Content-Type deve ser application/json"}, status_code=415)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response


def db():
    with SessionLocal() as session:
        yield session


@app.get("/healthz")
def healthz(session: Session = Depends(db)):
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(503, "Banco indisponível")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/assets/{name}", include_in_schema=False)
def assets(name: str):
    if name not in {"style.css", "app.js", "logo-turvo.png"}:
        raise HTTPException(404)
    media = "text/css" if name.endswith(".css") else "text/javascript" if name.endswith(".js") else "image/png"
    return FileResponse(STATIC / name, media_type=media)


@app.get("/api/summary")
def summary(session: Session = Depends(db)):
    today = date.today()
    all_contracts = session.scalar(select(func.count()).select_from(Contract)) or 0
    active = session.scalar(select(func.count()).select_from(Contract).where(Contract.end_date >= today, Contract.start_date <= today)) or 0
    upcoming = session.scalar(select(func.count()).select_from(Contract).where(Contract.end_date.between(today, today + timedelta(days=30)))) or 0
    expired = session.scalar(select(func.count()).select_from(Contract).where(Contract.end_date < today)) or 0
    unclassified = session.scalar(select(func.count()).select_from(Contract).where(Contract.secretary_id.is_(None))) or 0
    procurements = session.scalar(select(func.count()).select_from(Procurement)) or 0
    groups = session.execute(
        select(Secretary.name, func.count(Contract.id))
        .join(Contract, Contract.secretary_id == Secretary.id)
        .where(Contract.end_date.between(today, today + timedelta(days=60)))
        .group_by(Secretary.name)
        .order_by(func.count(Contract.id).desc())
    ).all()
    latest = session.scalar(select(SyncRun).order_by(SyncRun.id.desc()).limit(1))
    return {
        "all": all_contracts, "active": active, "upcoming": upcoming,
        "expired": expired, "unclassified": unclassified,
        "procurements": procurements,
        "by_secretary": [{"name": n, "count": count} for n, count in groups],
        "sync": {
            "status": latest.status,
            "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
            "error": latest.error,
        } if latest else None,
    }


@app.get("/api/contracts")
def contracts(
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    secretary_id: int | None = Query(None, ge=1),
    due_date: date | None = None,
    period: str = Query("all", pattern="^(all|30|60|90|expired|unknown)$"),
    session: Session = Depends(db),
):
    today = date.today()
    stmt = select(Contract)
    if q.strip():
        term = "%" + q.strip() + "%"
        stmt = stmt.where(or_(Contract.number.ilike(term), Contract.supplier.ilike(term), Contract.object.ilike(term)))
    if secretary_id is not None:
        stmt = stmt.where(Contract.secretary_id == secretary_id)
    if due_date is not None:
        stmt = stmt.where(Contract.end_date == due_date)
    if period in ("30", "60", "90"):
        stmt = stmt.where(Contract.end_date.between(today, today + timedelta(days=int(period))))
    elif period == "expired":
        stmt = stmt.where(Contract.end_date < today)
    elif period == "unknown":
        stmt = stmt.where(Contract.end_date.is_(None))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = session.scalars(
        stmt.options(joinedload(Contract.secretary))
        .order_by(Contract.end_date.is_(None), Contract.end_date, Contract.id)
        .offset((page - 1) * limit).limit(limit)
    ).all()
    return {"total": total, "page": page, "items": [serialize_contract(c) for c in result]}



@app.get("/api/calendar")
def calendar(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    secretary_id: int | None = Query(None, ge=1),
    session: Session = Depends(db),
):
    """Contagem integral de vencimentos por dia: não depende da paginação da tabela."""
    year, month_number = map(int, month.split("-"))
    if year < 2021 or year > 2100:
        raise HTTPException(422, "Mês fora do intervalo permitido")
    first_day = date(year, month_number, 1)
    next_month = date(year + 1, 1, 1) if month_number == 12 else date(year, month_number + 1, 1)
    stmt = select(Contract).options(joinedload(Contract.secretary)).where(
        Contract.end_date >= first_day, Contract.end_date < next_month
    )
    if secretary_id is not None:
        stmt = stmt.where(Contract.secretary_id == secretary_id)
    grouped = {}
    for contract in session.scalars(stmt.order_by(Contract.end_date, Contract.id)).all():
        grouped.setdefault(contract.end_date.isoformat(), []).append(serialize_contract(contract))
    days = [{"date": due, "count": len(items), "items": items} for due, items in grouped.items()]
    return {"month": month, "total": sum(x["count"] for x in days), "days": days}


@app.get("/api/procurements")
def procurements(
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(db),
):
    stmt = select(Procurement)
    if q.strip():
        term = "%" + q.strip() + "%"
        stmt = stmt.where(or_(Procurement.number.ilike(term), Procurement.object.ilike(term), Procurement.process.ilike(term)))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(Procurement.published_at.desc(), Procurement.id.desc())
        .offset((page - 1) * limit).limit(limit)
    ).all()
    return {"total": total, "page": page, "items": [serialize_procurement(row) for row in rows]}


@app.get("/api/secretaries")
def secretaries(session: Session = Depends(db)):
    rows = session.scalars(select(Secretary).order_by(Secretary.name)).all()
    return [{"id": s.id, "name": s.name, "email": s.email} for s in rows]


class NewSecretary(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    email: str | None = Field(default=None, max_length=250)


@app.post("/api/secretaries", status_code=201)
def create_secretary(item: NewSecretary, session: Session = Depends(db)):
    name = item.name.strip()
    email = (item.email or "").strip() or None
    if email and (email.count("@") != 1 or "\n" in email or "\r" in email or " " in email):
        raise HTTPException(422, "E-mail inválido")
    if session.scalar(select(Secretary).where(Secretary.name == name)):
        raise HTTPException(409, "Secretaria já cadastrada")
    row = Secretary(name=name, email=email)
    session.add(row)
    session.add(AuditEvent(actor=os.getenv("DASHBOARD_USERNAME", "admin"), action="create_secretary", details={"name": name, "email": email}))
    session.commit()
    return {"id": row.id, "name": row.name}


class Classification(BaseModel):
    secretary_id: int | None = None


@app.post("/api/contracts/{contract_id}/secretary")
def assign_secretary(contract_id: int, body: Classification, session: Session = Depends(db)):
    contract = session.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "Contrato não encontrado")
    if body.secretary_id is not None and not session.get(Secretary, body.secretary_id):
        raise HTTPException(404, "Secretaria não encontrada")
    previous = contract.secretary_id
    contract.secretary_id = body.secretary_id
    session.add(AuditEvent(actor=os.getenv("DASHBOARD_USERNAME", "admin"), action="assign_secretary",
                           details={"contract_id": contract_id, "previous": previous, "new": body.secretary_id}))
    session.commit()
    return {"ok": True}


@app.get("/api/sync")
def synchronization(session: Session = Depends(db)):
    recent = session.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(10)).all()
    cursor = session.get(SyncState, "publication")
    return {
        "next_publication_day": cursor.next_day.isoformat() if cursor else None,
        "runs": [{
            "kind": r.kind, "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status, "processed": r.processed, "error": r.error,
        } for r in recent]
    }
