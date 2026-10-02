"""Importadores com arquivos sintéticos no formato oficial (sem tocar nas bases reais)."""
import gzip
from datetime import date

from sqlalchemy import func, select

from app.extensions import db
from app.ingestion import zarc, zarc_cultivars
from app.models import DatasetVersion, VarietyZone, ZarcWindow, ZarcZone
from tests.conftest import ARARAQUARA

HEADER = (
    "Nome_cultura;SafraIni;SafraFin;Cod_Cultura;Cod_Ciclo;Cod_Solo;geocodigo;UF;municipio;Cod_Clima;"
    "Nome_Clima;Cod_Outros_Manejos;Nome_Outros_Manejos;Produtividade;Cod_NM;Cod_Munic;Cod_Meso;Cod_Micro;Portaria;"
    + ";".join(f"dec{i}" for i in range(1, 37))
)


def row(name, soil, ibge, decs: dict, nm="", cycle=20):
    vals = [str(decs.get(i, 0)) for i in range(1, 37)]
    return (
        f"{name};2026;2027;1;{cycle};{soil};{ibge};SP;X;0;Não se aplica;1;Sequeiro;;{nm};1;1;1;Port.9;"
        + ";".join(vals)
    )


def write_csv(path, rows):
    path.write_text("﻿" + HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_zarc_import_long_format_versioning_and_idempotency(app, tmp_path):
    f = tmp_path / "tabua.csv"
    write_csv(
        f,
        [
            row("Soja", 2, ARARAQUARA, {28: 20, 29: 30}, nm="1"),
            row("Soja", 2, ARARAQUARA, {28: 40}, nm="2"),  # nível de manejo diferente → outra zona
            row("Soja", 2, ARARAQUARA, {28: 40}, nm="2"),  # duplicada → descartada
            row("Sorgo Forrageiro", 2, ARARAQUARA, {28: 20}),  # fora do MVP
            row("Soja", 2, 9999999, {28: 20}),  # município inexistente
            row("Soja", 99, ARARAQUARA, {28: 20}),  # solo inexistente
        ],
    )
    report = zarc.run([f], extracted_at=date(2026, 10, 2), chunksize=2)
    assert report.status == "active"
    assert report.rows_loaded == 2
    assert report.skipped_reasons["zona_duplicada"] == 1
    assert report.skipped_reasons["cultura_fora_do_mvp"] == 1
    assert report.skipped_reasons["municipio_desconhecido"] == 1
    assert report.skipped_reasons["solo_desconhecido"] == 1

    v = db.session.get(DatasetVersion, report.version_id)
    assert v.is_current and v.version_label == "Safra 2026/2027"
    zone_ids = select(ZarcZone.id).where(ZarcZone.dataset_version_id == v.id)
    n_windows = db.session.scalar(select(func.count()).select_from(ZarcWindow).where(ZarcWindow.zone_id.in_(zone_ids)))
    assert n_windows == 3  # só decêndios com risco > 0

    # mesma entrada → no-op
    again = zarc.run([f], extracted_at=date(2026, 10, 2))
    assert again.status == "unchanged"

    # nova versão substitui a anterior (que fica superseded, não é apagada)
    f2 = tmp_path / "tabua2.csv"
    write_csv(f2, [row("Soja", 2, ARARAQUARA, {30: 20})])
    new = zarc.run([f2], extracted_at=date(2026, 10, 3))
    db.session.refresh(v)
    assert v.status == "superseded" and not v.is_current
    assert db.session.get(DatasetVersion, new.version_id).is_current


def test_cultivars_import_by_uf(app, tmp_path):
    f = tmp_path / "cult.csv.gz"
    content = (
        "﻿Safra;Cultura;Obtentor_Mantenedor;Cultivar;UF;Grupo;Regiao_de_Adaptacao\n"
        "2026-2027;Milho;Embrapa;BRS Nova;SP;1;\n"
        "2026-2027;Feijão Caupi;Embrapa;BRS Tumucumaque;SP;0;\n"
        "2026-2027;Café;X;Catuaí;SP;0;\n"
        "2025-2026;Milho;Embrapa;Antiga;SP;1;\n"
    )
    with gzip.open(f, "wt", encoding="utf-8") as fh:
        fh.write(content)
    report = zarc_cultivars.run(f, chunksize=2)
    assert report.status == "active"
    assert report.extra["safras"] == "2026-2027"
    assert report.rows_loaded == 2
    zones = db.session.scalar(
        select(func.count()).select_from(VarietyZone).where(VarietyZone.dataset_version_id == report.version_id)
    )
    assert zones == 2


def test_cultivar_crop_matching_prefers_specific_rule(app):
    rules = zarc_cultivars._rules(None)
    caupi = zarc_cultivars.match_crop("Feijão Caupi", rules)
    feijao = zarc_cultivars.match_crop("Feijão", rules)
    assert caupi and feijao and caupi != feijao
    assert zarc_cultivars.match_crop("Café", rules) is None
