"""Comandos de operação: `flask data ...`. Só chamam ingestion/services."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import click
from flask.cli import AppGroup

from app.ingestion import catalog_seed, ibge_municipios, zarc, zarc_cultivars
from app.repositories import source_repo


data_cli = AppGroup("data", help="Importação e versionamento das bases oficiais.")


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


@data_cli.command("list-versions")
@click.option("--dataset", default=None)
def list_versions(dataset):
    for ds, v in source_repo.versions(dataset):
        mark = "*" if v.is_current else " "
        click.echo(
            f"{mark} {ds.code:<20} #{v.id:<4} {v.status:<10} {v.version_label:<40} "
            f"linhas={v.row_count:<8} extraído={v.extracted_at}"
        )
