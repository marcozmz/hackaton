"""Comandos de operação: `flask data ...`. Só chamam ingestion/services."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import click
from flask import current_app
from flask.cli import AppGroup

from app.config import BASE_DIR, INSTANCE_DIR
from app.extensions import db
from app.ingestion import (
    catalog_seed,
    download,
    ibge_malhas,
    ibge_municipios,
    maintenance,
    sisser,
    zarc,
    zarc_cultivars,
)
from app.repositories import source_repo

data_cli = AppGroup("data", help="Importação e versionamento das bases oficiais.")

DEFAULT_RAW = BASE_DIR / "data" / "raw"  # bases oficiais baixadas (fora do git)
CULTIVAR_SEASON = "2026-2027"


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@data_cli.command("seed")
def seed():
    """Fontes, solos, culturas e aliases (app/seeds/*.yaml)."""
    click.echo(f"datasets: {catalog_seed.seed_sources()}")
    click.echo(f"solos: {catalog_seed.seed_soils()}")
    crops, aliases = catalog_seed.seed_crops()
    click.echo(f"culturas: {crops} · novos aliases: {aliases}")


@data_cli.command("import-municipios")
@click.option("--municipios", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--estados", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--extracted-at", default=None, help="AAAA-MM-DD (padrão: data do arquivo)")
def import_municipios(municipios, estados, extracted_at):
    click.echo(ibge_municipios.run(municipios, estados, _date(extracted_at)).render())


@data_cli.command("import-zarc")
@click.option("--file", "files", multiple=True, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--crops", default=None, help="slugs separados por vírgula (padrão: todas do catálogo)")
@click.option("--label", default=None)
@click.option("--extracted-at", default=None)
def import_zarc(files, crops, label, extracted_at):
    only = set(crops.split(",")) if crops else None
    click.echo(zarc.run(list(files), only, label, _date(extracted_at)).render())


@data_cli.command("import-zarc-cultivares")
@click.option("--file", "file", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--season", "seasons", multiple=True, help="ex.: 2026-2027 (padrão: a mais recente)")
@click.option("--crops", default=None)
@click.option("--extracted-at", default=None)
def import_cultivares(file, seasons, crops, extracted_at):
    only = set(crops.split(",")) if crops else None
    click.echo(zarc_cultivars.run(file, list(seasons) or None, only, _date(extracted_at)).render())


@data_cli.command("import-sisser")
@click.option("--file", "files", multiple=True, required=True, type=click.Path(exists=True, path_type=Path),
              help="uma planilha por ano (ex.: dados_abertos_psr_2025_sisser.xlsx)")
@click.option("--extracted-at", default=None)
def import_sisser(files, extracted_at):
    """Seguro rural (PSR): lê só colunas não pessoais e grava agregados."""
    click.echo(sisser.run(list(files), _date(extracted_at)).render())


@data_cli.command("import-malhas")
@click.option("--uf", "ufs", multiple=True, help="UFs (padrão: todas). Ex.: --uf SP --uf MG")
def import_malhas(ufs):
    """Limites municipais do IBGE (GeoJSON por UF) para o mapa."""
    geo_dir = Path(current_app.config["GEO_DIR"])
    click.echo(ibge_malhas.run(geo_dir, list(ufs) or None).render())


@data_cli.command("download")
@click.option("--dir", "raw_dir", default=str(DEFAULT_RAW), type=click.Path(path_type=Path), show_default=True)
@click.option("--only", multiple=True, help="parte do nome do arquivo (ex.: --only sisser)")
def download_cmd(raw_dir, only):
    """Baixa as bases oficiais (MAPA, IBGE) com retomada. Pode demorar: o portal do MAPA é lento."""
    download.download_all(raw_dir, list(only) or None, echo=click.echo)


@data_cli.command("bootstrap")
@click.option("--dir", "raw_dir", default=str(DEFAULT_RAW), type=click.Path(path_type=Path), show_default=True)
@click.option("--download/--no-download", "do_download", default=True, show_default=True,
              help="baixar o que faltar antes de importar")
def bootstrap(raw_dir, do_download):
    """Monta o banco do zero: download → seeds → municípios → ZARC → cultivares → SISSER → malhas."""
    raw = Path(raw_dir)
    if do_download:
        click.echo("== 1/7 download das bases"); download.download_all(raw, echo=click.echo)
    click.echo("== 2/7 seeds"); seed.callback()
    click.echo("== 3/7 municípios IBGE")
    click.echo(ibge_municipios.run(raw / "ibge_municipios.csv", raw / "ibge_estados.csv").render())
    click.echo("== 4/7 ZARC (safra 2026/27 + perenes) — alguns minutos")
    click.echo(zarc.run([raw / "tabua-de-risco-safra-2026-2027.csv",
                         raw / "tabua-de-risco-perene-olericola-sem-safra.csv"]).render())
    click.echo("== 5/7 ZARC cultivares — reduzindo o arquivo oficial (alguns minutos)")
    reduced = raw / f"cultivares_{CULTIVAR_SEASON}.csv.gz"
    if not reduced.exists():
        r = zarc_cultivars.extract_distinct(raw / "siszarc_cronograma.csv.gz", reduced, [CULTIVAR_SEASON])
        click.echo(f"  lidas={r['read']} distintas={r['distinct']} truncado={r['truncated']}")
    click.echo(zarc_cultivars.run(reduced, [CULTIVAR_SEASON]).render())
    click.echo("== 6/7 SISSER (seguro rural, agregado)")
    click.echo(sisser.run([raw / "dados_abertos_psr_2025_sisser.xlsx"]).render())
    click.echo("== 7/7 malhas municipais (mapa)")
    click.echo(ibge_malhas.run(Path(current_app.config["GEO_DIR"])).render())
    click.echo("Pronto. Rode `flask run` e abra http://127.0.0.1:5000")


@data_cli.command("prune")
def prune():
    """Apaga os dados de versões antigas (superseded/failed) para diminuir o banco."""
    click.echo(maintenance.prune_superseded())


@data_cli.command("export-db")
@click.option("--out", default="plantefacil-db.zip", type=click.Path(path_type=Path), show_default=True)
def export_db(out):
    """Empacota o banco pronto (compactado) + malhas do mapa num .zip para a equipe."""
    click.echo(maintenance.export_db(out, Path(current_app.config["GEO_DIR"])))


@data_cli.command("import-db")
@click.option("--file", "zip_path", required=True, type=click.Path(exists=True, path_type=Path))
def import_db(zip_path):
    """Restaura o .zip gerado por export-db em backend/instance (substitui o banco local)."""
    db.session.remove()
    db.engine.dispose()
    click.echo(maintenance.import_db(zip_path, INSTANCE_DIR))


@data_cli.command("list-versions")
@click.option("--dataset", default=None)
def list_versions(dataset):
    for ds, v in source_repo.versions(dataset):
        mark = "*" if v.is_current else " "
        click.echo(
            f"{mark} {ds.code:<20} #{v.id:<4} {v.status:<10} {v.version_label:<40} "
            f"linhas={v.row_count:<8} extraído={v.extracted_at}"
        )
