"""SISSER: privacidade (só agregados, k-anonimato) + bloco "proteja sua safra"."""
from openpyxl import Workbook
from sqlalchemy import inspect, select

from app.extensions import db
from app.ingestion import sisser
from app.models import InsuranceStat
from tests.conftest import ARARAQUARA, ARARAS

HEADER = [
    "NM_RAZAO_SOCIAL", "NM_SEGURADO", "NR_DOCUMENTO_SEGURADO", "NR_PROPOSTA", "NR_APOLICE",
    "NR_DECIMAL_LATITUDE", "NR_DECIMAL_LONGITUDE", "NM_CULTURA_GLOBAL", "CD_GEOCMU", "ANO_APOLICE",
    "NR_AREA_TOTAL", "VL_LIMITE_GARANTIA", "VL_PREMIO_LIQUIDO", "VL_SUBVENCAO_FEDERAL", "VALOR_INDENIZAÇÃO",
]


def policy(name, crop, ibge, area=10.0):
    return ["Seguradora X", name, "123.456.789-00", "P1", "A1", -21.7, -48.1, crop, ibge, 2025,
            area, 10000.0, 1000.0, 400.0, "-"]


def make_xlsx(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)


def load(tmp_path):
    f = tmp_path / "psr.xlsx"
    make_xlsx(f, [
        *[policy(f"Fulano {i}", "Milho 2ª safra", ARARAQUARA) for i in range(4)],  # 4 → mostra município
        policy("Beltrano", "Milho 2ª safra", ARARAS),  # 1 → suprimido no município
        policy("Ciclano", "Uva", ARARAS),
        policy("Sem município", "Milho 2ª safra", "-"),
    ])
    return sisser.run([f])


def test_import_keeps_only_aggregates(app, tmp_path):
    report = load(tmp_path)
    assert report.status == "active" and report.skipped_reasons["municipio_invalido"] == 1
    cols = {c["name"] for c in inspect(db.engine).get_columns("insurance_stat")}
    forbidden = {"name", "document", "cpf", "segurado", "latitude", "longitude", "apolice", "proposta"}
    assert not any(f in c.lower() for c in cols for f in forbidden)
    dumped = " ".join(str(v) for s in db.session.scalars(select(InsuranceStat)) for v in vars(s).values())
    assert "Fulano" not in dumped and "123.456" not in dumped


def test_municipality_scope_when_enough_policies(client, tmp_path):
    load(tmp_path)
    body = client.get("/api/v1/insurance/summary", query_string={"municipality": ARARAQUARA, "crop": "milho"}).get_json()
    assert body["status"] == "ok" and body["scope"] == "municipality" and body["policies_count"] == 4
    assert body["subsidy_share_pct"] == 40.0 and body["avg_premium_rate_pct"] == 10.0


def test_small_cell_is_suppressed_to_state(client, tmp_path):
    load(tmp_path)
    body = client.get("/api/v1/insurance/summary", query_string={"municipality": ARARAS, "crop": "milho"}).get_json()
    assert body["scope"] == "uf" and body["scope_name"] == "SP" and body["policies_count"] == 5


def test_recommendation_includes_insurance_and_action(client, tmp_path):
    load(tmp_path)
    body = client.get("/api/v1/recommendations/planting",
                      query_string={"municipality": ARARAQUARA, "crop": "milho", "soil": "2", "date": "2026-10-02"}).get_json()
    assert body["insurance"]["status"] == "ok" and "4 seguros" in body["insurance"]["text"]
    assert any("seguro rural" in a for a in body["actions"])
    assert "sisser" in {s["id"] for s in body["sources"]}
    assert body["status"] == "favorable"  # informativo: não altera o risco


def test_insurance_unavailable_when_not_loaded(client):
    body = client.get("/api/v1/insurance/summary", query_string={"municipality": ARARAQUARA, "crop": "milho"}).get_json()
    assert body["status"] == "unavailable"
