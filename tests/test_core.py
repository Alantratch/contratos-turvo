from datetime import date, timedelta
from app.core import (
    Base, Contract, ContractRevision, ContractTerm, ContractTermRevision, Procurement, Secretary, SessionLocal, SyncRun,
    auto_classify_contract_units, engine, parse_date, serialize_contract, serialize_procurement, upsert_contract,
    upsert_contract_term, upsert_procurement, valid_cnpj,
)
from app.worker import alert_threshold, compras_pages, equiplano_amount, equiplano_date_range, equiplano_object, equiplano_payload, equiplano_supplier_index, equiplano_table
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


def test_cnpj_validation_rejects_malformed_target():
    assert valid_cnpj("78.279.973/0001-07")
    assert not valid_cnpj("78279973000108")
    assert not valid_cnpj("")


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


def test_effective_fields_revert_to_base_when_latest_term_is_excluded():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        payload = sample()
        payload["numeroControlePNCP"] = "78279973000107-2-00002/2026"
        upsert_contract(db, payload)
        contract = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        term = {
            "sequencialTermoContrato": 1,
            "dataVigenciaFim": "2027-06-30",
            "qualificacaoVigencia": True,
        }
        upsert_contract_term(db, contract, term)
        assert contract.end_date == date(2027, 6, 30)
        term["excluido"] = True
        assert upsert_contract_term(db, contract, term) == "updated"
        assert contract.end_date == date(2026, 12, 31)


def test_contract_update_reapplies_active_term_after_reload():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        payload = sample()
        payload["numeroControlePNCP"] = "78279973000107-2-00003/2026"
        upsert_contract(db, payload)
        contract = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        upsert_contract_term(db, contract, {
            "sequencialTermoContrato": 1,
            "dataVigenciaFim": "2027-06-30",
            "valorGlobal": 150.25,
            "qualificacaoVigencia": True,
            "qualificacaoAcrescimoSupressao": True,
        })
        db.commit()

        updated = dict(payload, objetoContrato="Objeto atualizado")
        assert upsert_contract(db, updated) == "updated"
        partial = {
            "numeroControlePNCP": payload["numeroControlePNCP"],
            "orgaoEntidade": {"cnpj": "78279973000107"},
        }
        assert upsert_contract(db, partial) == "unchanged"
        db.commit()

        stored = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        assert stored.supplier == "Fornecedor teste"
        assert stored.end_date == date(2027, 6, 30)
        assert stored.amount == 150.25


def test_partial_term_update_preserves_fields_and_parses_boolean_strings():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        payload = sample()
        payload["numeroControlePNCP"] = "78279973000107-2-00004/2026"
        upsert_contract(db, payload)
        contract = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        upsert_contract_term(db, contract, {
            "sequencialTermoContrato": 1,
            "dataVigenciaFim": "2027-06-30",
            "valorGlobal": 150.25,
            "qualificacaoVigencia": True,
            "qualificacaoAcrescimoSupressao": True,
        })
        assert upsert_contract_term(db, contract, {
            "sequencialTermoContrato": 1,
            "qualificacaoVigencia": "false",
            "excluido": "false",
        }) == "updated"
        db.commit()

        term = db.scalar(select(ContractTerm).where(ContractTerm.term_key == f"{payload['numeroControlePNCP']}#termo-1"))
        stored = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        assert term.end_date == date(2027, 6, 30)
        assert term.excluded is False
        assert term.qualifies_duration is False
        assert stored.end_date == date(2026, 12, 31)
        assert stored.amount == 150.25
        assert db.scalar(select(ContractTermRevision).where(ContractTermRevision.term_id == term.id)).raw["dataVigenciaFim"] == "2027-06-30"


def test_explicit_null_preserves_canonical_contract_and_term_payload():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        payload = sample()
        payload["numeroControlePNCP"] = "78279973000107-2-00016/2026"
        upsert_contract(db, payload)
        contract = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        upsert_contract_term(db, contract, {
            "sequencialTermoContrato": 1,
            "dataVigenciaFim": "2027-06-30",
            "valorGlobal": 150.25,
            "qualificacaoVigencia": True,
            "qualificacaoAcrescimoSupressao": True,
        })
        upsert_contract(db, {
            "numeroControlePNCP": payload["numeroControlePNCP"],
            "orgaoEntidade": {"cnpj": "78279973000107"},
            "dataVigenciaFim": None,
            "valorGlobal": None,
            "unidadeOrgao": {"codigoUnidade": "9"},
        })
        upsert_contract_term(db, contract, {
            "sequencialTermoContrato": 1,
            "dataVigenciaFim": None,
            "valorGlobal": None,
        })
        db.commit()

        stored = db.scalar(select(Contract).where(Contract.pncp_key == payload["numeroControlePNCP"]))
        term = db.scalar(select(ContractTerm).where(ContractTerm.term_key == f"{payload['numeroControlePNCP']}#termo-1"))
        assert stored.raw["unidadeOrgao"]["nomeUnidade"] == "Município"
        assert stored.unit_code == "9"
        assert stored.raw["dataVigenciaFim"] == "2026-12-31"
        assert stored.end_date == date(2027, 6, 30)
        assert term.raw["dataVigenciaFim"] == "2027-06-30"
        assert term.end_date == date(2027, 6, 30)
        assert stored.amount == 150.25


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
        "dataAberturaPropostaPncp": "2026-01-01T08:00:00",
        "dataPublicacaoPncp": "2026-01-01T10:00:00",
        "existeResultado": True,
    }
    with SessionLocal() as db:
        assert upsert_procurement(db, payload) == "inserted"
        db.commit()
        stored = db.scalar(select(Procurement).where(Procurement.source_key == payload["numeroControlePNCP"]))
        assert stored is not None
        assert stored.opening_date == date(2026, 1, 1)
        assert serialize_procurement(stored)["phase"] == "result"
        assert upsert_procurement(db, {
            "numeroControlePNCP": payload["numeroControlePNCP"],
            "orgaoEntidadeCnpj": "78279973000107",
            "existeResultado": "false",
        }) == "updated"
        db.commit()
        assert stored.result_exists is False
        assert stored.opening_date == date(2026, 1, 1)


def test_licitacoes_api_groups_date_and_links_published_contract():
    from fastapi.testclient import TestClient
    procurement_key = "78279973000107-1-00008/2027"
    procurement = {
        "numeroControlePNCP": procurement_key,
        "orgaoEntidadeCnpj": "78279973000107",
        "numeroCompra": "90008",
        "anoCompraPncp": 2027,
        "sequencialCompraPncp": 8,
        "modalidadeNome": "Pregão - Eletrônico",
        "situacaoCompraNomePncp": "Divulgada no PNCP",
        "objetoCompra": "Objeto da licitação",
        "processo": "8/2027",
        "valorTotalEstimado": 1000,
        "dataAberturaPropostaPncp": "2027-12-15T08:00:00",
        "dataEncerramentoPropostaPncp": "2027-12-20T08:30:00",
        "existeResultado": False,
        "informacaoComplementar": "Consulte https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/landing?destino=quadro-informativo&compra=782799730001072027",
    }
    contract = sample()
    contract["numeroControlePNCP"] = "78279973000107-2-00008/2027"
    contract["numeroControlePncpCompra"] = procurement_key
    with SessionLocal() as db:
        assert upsert_procurement(db, procurement) == "inserted"
        assert upsert_contract(db, contract) == "inserted"
        db.commit()
    with TestClient(__import__("app.main", fromlist=["app"]).app) as client:
        response = client.get("/api/licitacoes?month=2027-12", auth=("test", "test-password"))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["days"][0]["date"] == "2027-12-15"
    item = data["days"][0]["items"][0]
    assert item["phase"] == "scheduled"
    assert item["impugnation_url"].startswith("https://cnetmobile")
    assert item["contracts"][0]["pncp_key"] == contract["numeroControlePNCP"]
    assert data["items"][0]["result_label"] == "Ainda não ocorreu"


def test_licitacoes_year_catalog_keeps_undated_and_classifies_in_progress():
    from fastapi.testclient import TestClient
    today = date.today()
    in_progress_key = f"78279973000107-1-09998/{today.year}"
    undated_key = f"78279973000107-1-09999/{today.year}"
    contracted_key = f"78279973000107-1-09997/{today.year}"
    in_progress = {
        "numeroControlePNCP": in_progress_key,
        "orgaoEntidadeCnpj": "78279973000107",
        "numeroCompra": "9998",
        "anoCompraPncp": today.year,
        "sequencialCompraPncp": 9998,
        "modalidadeNome": "Pregão - Eletrônico",
        "situacaoCompraNomePncp": "Divulgada no PNCP",
        "objetoCompra": "Licitação em andamento",
        "processo": "9998/2026",
        "dataAberturaPropostaPncp": (today - timedelta(days=10)).isoformat(),
        "dataEncerramentoPropostaPncp": (today + timedelta(days=10)).isoformat(),
        "existeResultado": False,
    }
    undated = dict(in_progress)
    undated.update({
        "numeroControlePNCP": undated_key,
        "numeroCompra": "9999",
        "sequencialCompraPncp": 9999,
        "objetoCompra": "Licitação sem data de abertura",
        "dataAberturaPropostaPncp": None,
        "dataEncerramentoPropostaPncp": None,
    })
    contracted = dict(in_progress)
    contracted.update({
        "numeroControlePNCP": contracted_key,
        "numeroCompra": "9997",
        "sequencialCompraPncp": 9997,
        "objetoCompra": "Licitação com contrato publicado",
        "dataAberturaPropostaPncp": (today - timedelta(days=30)).isoformat(),
        "dataEncerramentoPropostaPncp": (today - timedelta(days=20)).isoformat(),
    })
    contract = sample()
    contract["numeroControlePNCP"] = "78279973000107-2-09997/2026"
    contract["numeroControlePncpCompra"] = contracted_key
    with SessionLocal() as db:
        assert upsert_procurement(db, in_progress) == "inserted"
        assert upsert_procurement(db, undated) == "inserted"
        assert upsert_procurement(db, contracted) == "inserted"
        assert upsert_contract(db, contract) == "inserted"
        db.commit()
    with TestClient(__import__("app.main", fromlist=["app"]).app) as client:
        response = client.get(f"/api/licitacoes?year={today.year}", auth=("test", "test-password"))
    assert response.status_code == 200
    data = response.json()
    items = {item["source_key"]: item for item in data["items"]}
    assert items[in_progress_key]["phase"] == "in_progress"
    assert items[in_progress_key]["result_label"] == "Em andamento"
    assert items[contracted_key]["phase"] == "contracted"
    assert undated_key in items
    assert data["summary"]["undated"] >= 1
    assert all(item["source_key"] != undated_key for day in data["days"] for item in day["items"])


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
        assert client.get("/assets/vendor/bootstrap.min.css", auth=auth).status_code == 200


def test_contract_search_matches_all_supplier_words():
    from fastapi.testclient import TestClient
    payload = sample()
    payload["numeroControlePNCP"] = "78279973000107-2-00005/2026"
    payload["nomeRazaoSocialFornecedor"] = "IDS DESENVOLVIMENTO DE SOFTWARE E ASSESSORIA LTDA"
    with SessionLocal() as db:
        upsert_contract(db, payload)
        db.commit()
    with TestClient(__import__("app.main", fromlist=["app"]).app) as client:
        response = client.get("/api/contracts?q=IDS+SOFTWARE&period=all", auth=("test", "test-password"))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_contracts_prioritize_active_records_over_expired_records():
    from fastapi.testclient import TestClient
    today = date.today()
    active = sample()
    active["numeroControlePNCP"] = "78279973000107-2-00006/2026"
    active["nomeRazaoSocialFornecedor"] = "ORDER TEST ACTIVE"
    active["dataVigenciaInicio"] = (today - timedelta(days=30)).isoformat()
    active["dataVigenciaFim"] = (today + timedelta(days=30)).isoformat()
    expired = sample()
    expired["numeroControlePNCP"] = "78279973000107-2-00007/2026"
    expired["nomeRazaoSocialFornecedor"] = "ORDER TEST EXPIRED"
    expired["dataVigenciaInicio"] = (today - timedelta(days=60)).isoformat()
    expired["dataVigenciaFim"] = (today - timedelta(days=30)).isoformat()
    with SessionLocal() as db:
        upsert_contract(db, active)
        upsert_contract(db, expired)
        db.commit()
    with TestClient(__import__("app.main", fromlist=["app"]).app) as client:
        response = client.get("/api/contracts?q=ORDER+TEST&period=all", auth=("test", "test-password"))
        active_response = client.get("/api/contracts?q=ORDER+TEST&period=active", auth=("test", "test-password"))
    assert response.status_code == 200
    assert response.json()["items"][0]["supplier"] == "ORDER TEST ACTIVE"
    assert active_response.status_code == 200
    assert [item["supplier"] for item in active_response.json()["items"]] == ["ORDER TEST ACTIVE"]


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
    payload["numeroControlePNCP"] = "78279973000107-2-00015/2026"
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


def test_equiplano_rows_keep_supplier_object_dates_and_amount():
    html = """
    <table id="td"><tbody><tr>
      <td><a href="verContrato?formulario.idContrato=3015">abrir</a></td>
      <td>76</td><td></td><td>Contrato</td><td>Prestação de serviços</td><td></td>
      <td>22/04/2021 - 21/04/2022</td><td>22/04/2021 - 31/05/2027</td>
      <td>20 / 2021 - Pregão</td><td>185.280,00</td><td>Município de Turvo</td>
    </tr></tbody></table>
    """
    rows = equiplano_table(html)
    payload = equiplano_payload(2021, rows[0], {
        "supplier": "VIEIRA E RETECHESKI LTDA",
        "object": "Internet municipal",
    })
    assert payload["numeroControlePNCP"] == "equiplano:2021:3015"
    assert payload["dataVigenciaFim"] == "2022-04-21"
    assert payload["valorGlobal"] == "185280.00"
    assert payload["nomeRazaoSocialFornecedor"] == "VIEIRA E RETECHESKI LTDA"
    assert equiplano_date_range("27/05/2026 - 31/05/2027")[1] == date(2027, 5, 31)
    assert equiplano_amount("-83.618,84") == "-83618.84"
    assert equiplano_object(".") == ""

    export_rows = equiplano_table("""
      <table><tr><td>76</td><td></td><td>Contrato</td><td>Prestação</td><td></td>
      <td>22/04/2021 - 21/04/2022</td><td>22/04/2021 - 31/05/2027</td>
      <td>20 / 2021</td><td>185.280,00</td><td>Município de Turvo</td></tr></table>
    """)
    export_payload = equiplano_payload(2021, export_rows[0], {"supplier": "VIEIRA"})
    assert export_payload["numeroControlePNCP"] == "equiplano:2021:numero-76"


def test_equiplano_supplier_index_reads_more_than_one_page(monkeypatch):
    import httpx

    page_one = [
        ["codFornecedor=10", "", "Fornecedor A"],
        ["", "", "Contrato número 76", "100,00", "Objeto A"],
    ]
    page_two = [["", "", "Contrato número 77", "200,00", "Objeto B"]]
    starts = []

    def fake_server(request):
        starts.append(request.content.decode())
        rows = page_one if "start=0" in starts[-1] else page_two
        return httpx.Response(200, json={"paginacao": {"registrosAsJSONArray": rows, "recordsTotal": 3}}, request=request)

    monkeypatch.setattr("app.worker.time.sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(fake_server)) as client:
        index = equiplano_supplier_index(client, 2026)

    assert len(starts) == 2
    assert index[(2026, "76")]["supplier"] == "Fornecedor A"
    assert index[(2026, "77")]["object"] == "Objeto B"


def test_compras_pages_retries_transient_failure_and_accepts_204(monkeypatch):
    import httpx

    attempts = []

    def fake_server(request):
        attempts.append(request)
        if len(attempts) < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(204, request=request)

    monkeypatch.setattr("app.worker.time.sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(fake_server)) as client:
        assert list(compras_pages(client, 1, date(2026, 1, 1), date(2026, 1, 31))) == []
    assert len(attempts) == 3


def test_sync_terms_commits_each_contract_after_failure(monkeypatch):
    from app.worker import sync_terms

    Base.metadata.create_all(engine)
    keys = [f"78279973000107-2-000{number}/2026" for number in (17, 18, 19)]
    with SessionLocal() as db:
        for key in keys:
            payload = sample()
            payload["numeroControlePNCP"] = key
            upsert_contract(db, payload)
        db.commit()

    def fake_terms(_client, contract):
        if contract.pncp_key == keys[1]:
            raise RuntimeError("falha simulada")
        if contract.pncp_key not in keys:
            return []
        return [{
            "sequencialTermoContrato": 1,
            "dataVigenciaFim": "2027-06-30",
            "qualificacaoVigencia": True,
        }]

    monkeypatch.setattr("app.worker.contract_terms", fake_terms)
    sync_terms()

    with SessionLocal() as db:
        terms = db.scalars(select(ContractTerm).where(ContractTerm.term_key.in_([f"{key}#termo-1" for key in keys]))).all()
        run = db.scalar(select(SyncRun).where(SyncRun.kind == "terms").order_by(SyncRun.id.desc()))
        assert {term.term_key for term in terms} == {f"{keys[0]}#termo-1", f"{keys[2]}#termo-1"}
        assert run.status == "error"
        assert run.processed == 2


def test_summary_accepts_secretary_and_window_filters_and_returns_by_window():
    from fastapi.testclient import TestClient
    from app.main import app

    Base.metadata.create_all(engine)
    today = date.today()
    with SessionLocal() as db:
        area_a = db.scalar(select(Secretary).where(Secretary.name == "SECRETARIA DASHBOARD A"))
        if not area_a:
            area_a = Secretary(name="SECRETARIA DASHBOARD A")
            db.add(area_a)
        area_b = db.scalar(select(Secretary).where(Secretary.name == "SECRETARIA DASHBOARD B"))
        if not area_b:
            area_b = Secretary(name="SECRETARIA DASHBOARD B")
            db.add(area_b)
        db.flush()

        c30 = sample()
        c30["numeroControlePNCP"] = "78279973000107-2-00071/2026"
        c30["dataVigenciaInicio"] = (today - timedelta(days=10)).isoformat()
        c30["dataVigenciaFim"] = (today + timedelta(days=15)).isoformat()
        upsert_contract(db, c30)
        db.scalar(select(Contract).where(Contract.pncp_key == c30["numeroControlePNCP"])).secretary_id = area_a.id

        c60 = sample()
        c60["numeroControlePNCP"] = "78279973000107-2-00072/2026"
        c60["dataVigenciaInicio"] = (today - timedelta(days=10)).isoformat()
        c60["dataVigenciaFim"] = (today + timedelta(days=45)).isoformat()
        upsert_contract(db, c60)
        db.scalar(select(Contract).where(Contract.pncp_key == c60["numeroControlePNCP"])).secretary_id = area_a.id

        c90 = sample()
        c90["numeroControlePNCP"] = "78279973000107-2-00073/2026"
        c90["dataVigenciaInicio"] = (today - timedelta(days=10)).isoformat()
        c90["dataVigenciaFim"] = (today + timedelta(days=75)).isoformat()
        upsert_contract(db, c90)
        db.scalar(select(Contract).where(Contract.pncp_key == c90["numeroControlePNCP"])).secretary_id = area_b.id

        area_a_id = area_a.id
        area_b_id = area_b.id
        db.commit()

    auth = ("test", "test-password")
    with TestClient(app) as client:
        default_res = client.get("/api/summary", auth=auth)
        assert default_res.status_code == 200
        default_data = default_res.json()
        assert default_data["window"] == 60
        assert isinstance(default_data["by_window"], list)
        assert {b["key"] for b in default_data["by_window"]} == {"30", "60", "90", "active", "expired", "unknown"}

        filtered_30 = client.get(f"/api/summary?secretary_id={area_a_id}&window=30", auth=auth).json()
        assert filtered_30["secretary_id"] == area_a_id
        assert filtered_30["window"] == 30
        assert filtered_30["all"] == 2
        assert filtered_30["active"] == 2
        assert filtered_30["upcoming"] == 1
        assert filtered_30["by_secretary"] == [{"id": area_a_id, "name": "SECRETARIA DASHBOARD A", "count": 1}]
        buckets_a = {b["key"]: b["count"] for b in filtered_30["by_window"]}
        assert buckets_a["30"] == 1
        assert buckets_a["60"] == 1
        assert buckets_a["90"] == 0

        filtered_90 = client.get(f"/api/summary?secretary_id={area_b_id}&window=90", auth=auth).json()
        assert filtered_90["by_secretary"] == [{"id": area_b_id, "name": "SECRETARIA DASHBOARD B", "count": 1}]
        buckets_b = {b["key"]: b["count"] for b in filtered_90["by_window"]}
        assert buckets_b["90"] == 1

        assert client.get("/api/summary?window=45", auth=auth).status_code == 422
