from datetime import date
from app.core import Base, Contract, ContractRevision, SessionLocal, engine, parse_date, upsert_contract
from app.worker import alert_threshold
from sqlalchemy import select


def sample():
    return {
        "numeroControlePNCP": "78279973000107-2-00001/2026",
        "orgaoEntidade": {"cnpj": "78279973000107"},
        "numeroContratoEmpenho": "01/2026",
        "anoContrato": 2026,
        "sequencialContrato": 1,
        "unidadeOrgao": {"nomeUnidade": "Município", "codigoUnidade": "1"},
        "nomeRazaoSocialFornecedor": "Fornecedor teste",
        "objetoContrato": "Objeto teste",
        "valorGlobal": 100.25,
        "dataVigenciaInicio": "2026-01-01",
        "dataVigenciaFim": "2026-12-31",
    }


def test_upsert_idempotent_and_versions():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        payload = sample()
        assert upsert_contract(db, payload) == "inserted"
        db.commit()
        assert upsert_contract(db, payload) == "unchanged"
        payload["dataVigenciaFim"] = "2027-12-31"
        assert upsert_contract(db, payload) == "updated"
        db.commit()
        assert len(db.scalars(select(Contract)).all()) == 1
        assert len(db.scalars(select(ContractRevision)).all()) == 2


def test_other_municipality_is_ignored():
    with SessionLocal() as db:
        data = sample()
        data["orgaoEntidade"]["cnpj"] = "11111111000111"
        assert upsert_contract(db, data) == "ignored"


def test_dates_and_alert_levels():
    assert parse_date("2026-12-31T00:00:00") == date(2026, 12, 31)
    assert parse_date("invalid") is None
    assert alert_threshold(31) == 60
    assert alert_threshold(30) == 30
    assert alert_threshold(8) == 15
    assert alert_threshold(-1) is None
