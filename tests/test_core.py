from datetime import date
from app.core import (
    Base, Contract, ContractRevision, ContractTerm, Procurement, Secretary, SessionLocal,
    auto_classify_contract_units, engine, parse_date, serialize_contract, upsert_contract,
    upsert_contract_term, upsert_procurement,
)
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


def test_contract_terms_are_stored_and_update_effective_vigency():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        payload = sample()
        upsert_contract(db, payload)
        contract = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        term = {
            "sequencialTermoContrato": 1,
            "numeroTermoContrato": "1",
            "tipoTermoContrato": {"id": 2, "nome": "Termo aditivo"},
            "objetoTermoContrato": "Prorrogação da vigência",
            "dataAssinatura": "2026-12-01",
            "dataVigenciaInicio": "2026-01-01",
            "dataVigenciaFim": "2027-06-30",
            "dataPublicacaoPncp": "2026-12-02T10:00:00",
            "valorAcrescido": 50,
            "valorGlobal": 150.25,
            "prazoAditadoDias": 181,
            "qualificacaoAcrescimoSupressao": True,
            "qualificacaoVigencia": True,
        }
        assert upsert_contract_term(db, contract, term) == "inserted"
        db.commit()
        stored = db.scalar(select(Contract).where(Contract.id == contract.id))
        assert stored.end_date == date(2027, 6, 30)
        assert stored.amount == 150.25
        assert len(db.scalars(select(ContractTerm)).all()) == 1
        assert serialize_contract(stored)["terms_count"] == 1


def test_other_municipality_is_ignored():
    with SessionLocal() as db:
        data = sample()
        data["orgaoEntidade"]["cnpj"] = "11111111000111"
        assert upsert_contract(db, data) == "ignored"


def test_compras_procurement_is_stored_separately():
    Base.metadata.create_all(engine)
    payload = {
        "numeroControlePNCP": "78279973000107-1-00001/2026",
        "orgaoEntidadeCnpj": "78279973000107",
        "numeroCompra": "90001",
        "anoCompraPncp": 2026,
        "sequencialCompraPncp": 1,
        "modalidadeNome": "Pregão - Eletrônico",
        "situacaoCompraNomePncp": "Divulgada no PNCP",
        "objetoCompra": "Objeto da contratação",
        "processo": "1/2026",
        "valorTotalEstimado": 1000,
        "dataPublicacaoPncp": "2026-01-01T10:00:00",
    }
    with SessionLocal() as db:
        assert upsert_procurement(db, payload) == "inserted"
        db.commit()
        assert db.scalar(select(Procurement).where(Procurement.source_key == payload["numeroControlePNCP"])) is not None


def test_units_create_areas_but_skip_generic_municipality():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        specific = sample()
        specific["numeroControlePNCP"] = "78279973000107-2-00003/2026"
        specific["unidadeOrgao"] = {"nomeUnidade": "SECRETARIA DE SAUDE"}
        generic = sample()
        generic["numeroControlePNCP"] = "78279973000107-2-00004/2026"
        generic["unidadeOrgao"] = {"nomeUnidade": "PREFEITURA MUNICIPAL DE TURVO - PR"}
        upsert_contract(db, specific)
        upsert_contract(db, generic)
        assert auto_classify_contract_units(db) >= 1
        db.commit()
        area = db.scalar(select(Secretary).where(Secretary.name == "SECRETARIA DE SAUDE"))
        assert area is not None
        assert db.scalar(select(Contract).where(Contract.pncp_key == specific["numeroControlePNCP"])).secretary_id == area.id
        assert db.scalar(select(Contract).where(Contract.pncp_key == generic["numeroControlePNCP"])).secretary_id is None


def test_dates_and_alert_levels():
    assert parse_date("2026-12-31T00:00:00") == date(2026, 12, 31)
    assert parse_date("invalid") is None
    assert alert_threshold(31) == 60
    assert alert_threshold(30) == 30
    assert alert_threshold(8) == 15
    assert alert_threshold(-1) is None


def test_api_requires_auth_and_serves_dashboard():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/").status_code == 401
        auth = ("test", "test-password")
        assert client.get("/", auth=auth).status_code == 200
        assert client.get("/api/summary", auth=auth).status_code == 200
        assert client.get("/assets/app.js", auth=auth).status_code == 200


def test_pncp_adapter_pagination_and_cnpj_filter():
    import httpx
    from app.worker import pages
    payload = sample()

    def fake_server(request):
        assert request.url.params["cnpjOrgao"] == "78279973000107"
        assert request.url.params["pagina"] == "1"
        return httpx.Response(200, json={"data": [payload], "totalPaginas": 1})

    with httpx.Client(transport=httpx.MockTransport(fake_server)) as client:
        batches = list(pages(client, "/contratos", date(2026, 10, 1), date(2026, 10, 31)))
    assert len(batches) == 1
    assert batches[0][0]["numeroControlePNCP"] == payload["numeroControlePNCP"]


def test_pncp_adapter_accepts_no_content():
    import httpx
    from app.worker import pages

    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(204))) as client:
        assert list(pages(client, "/contratos", date(2026, 10, 1), date(2026, 10, 31))) == []


def test_pncp_terms_adapter_accepts_no_content():
    import httpx
    from app.worker import contract_terms

    contract = Contract(year=2026, sequence=1, pncp_key="78279973000107-2-00001/2026")
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(204))) as client:
        assert contract_terms(client, contract) == []


def test_calendar_api_counts_dates_and_filters():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core import Secretary
    payload = sample()
    payload["dataVigenciaFim"] = "2027-12-31"
    with SessionLocal() as db:
        upsert_contract(db, payload)
        db.commit()
    with TestClient(app) as client:
        auth = ("test", "test-password")
        response = client.get("/api/calendar?month=2027-12", auth=auth)
        assert response.status_code == 200
        data = response.json()
        assert data["month"] == "2027-12"
        assert any(d["date"] == "2027-12-31" and d["count"] >= 1 for d in data["days"])
        detail = client.get("/api/contracts?due_date=2027-12-31", auth=auth)
        assert detail.status_code == 200
        assert detail.json()["total"] >= 1
        assert all(c["end_date"] == "2027-12-31" for c in detail.json()["items"])
        assert client.get("/api/calendar?month=2027-13", auth=auth).status_code == 422
        assert client.get("/api/calendar?month=2027-12").status_code == 401
        assert client.get("/api/calendar?month=2027-12&secretary_id=999999", auth=auth).json()["total"] == 0


def test_calendar_returns_all_contracts_and_objects_for_a_day():
    from fastapi.testclient import TestClient
    second = sample()
    second["numeroControlePNCP"] = "78279973000107-2-00002/2026"
    second["sequencialContrato"] = 2
    second["objetoContrato"] = "Segundo objeto"
    with SessionLocal() as db:
        upsert_contract(db, sample())
        upsert_contract(db, second)
        db.commit()
    with TestClient(__import__("app.main", fromlist=["app"]).app) as client:
        data = client.get("/api/calendar?month=2026-12", auth=("test", "test-password")).json()
    day = next(d for d in data["days"] if d["date"] == "2026-12-31")
    assert day["count"] >= 2
    assert {item["object"] for item in day["items"]} >= {"Objeto teste", "Segundo objeto"}
