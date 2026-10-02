"""Baixa as bases oficiais para uma pasta local (padrão: ../../arquivos).

O portal do MAPA recusa clientes sem user-agent de navegador, derruba conexões longas e às
vezes trava sem fechar: baixamos em streaming, com retomada (HTTP Range), detecção de
travamento e várias tentativas. Saída: só o progresso resumido (nunca o conteúdo).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MAPA = "https://dados.agricultura.gov.br/dataset"


@dataclass(frozen=True)
class Source:
    file: str
    url: str
    allow_truncated: bool = False  # o arquivo de cultivares costuma vir incompleto do portal
    note: str = ""


SOURCES = [
    Source("ibge_municipios.csv", "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"),
    Source("ibge_estados.csv", "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/estados.csv"),
    Source(
        "tabua-de-risco-safra-2026-2027.csv",
        f"{MAPA}/6d3d141c-885e-41a4-ab7f-dc8ff323b96f/resource/139e5a60-1f43-4cc8-aeab-a35dbbf816c0/download/dados-abertos-tabua-de-risco-safra-2026-2027.csv",
    ),
    Source(
        "tabua-de-risco-perene-olericola-sem-safra.csv",
        f"{MAPA}/6d3d141c-885e-41a4-ab7f-dc8ff323b96f/resource/dae65d31-683f-4ac4-ab90-3abd0c1583ba/download/dados-abertos-tabua-de-risco-safra-perene-olericola-sem-safra.csv",
    ),
    Source(
        "siszarc_cronograma.csv.gz",
        f"{MAPA}/d68e269e-dbe5-44d9-83ec-1f0871427773/resource/97038867-7afc-4f93-85ef-f39cf8368581/download/siszarc_cronograma.csv.gz",
        allow_truncated=True,
        note="~1 GB; o portal costuma entregar truncado — o importador aproveita o que for legível",
    ),
    Source(
        "dados_abertos_psr_2025_sisser.xlsx",
        f"{MAPA}/baefdc68-9bad-4204-83e8-f2888b79ab48/resource/b904117d-b758-406d-92ef-4c7762017c61/download/dados_abertos_psr_2025.xlsx",
    ),
]


def _remote_size(url: str) -> int | None:
    try:
        r = requests.head(url, headers={"User-Agent": UA}, allow_redirects=True, timeout=(10, 30))
        size = int(r.headers.get("Content-Length", "0"))
        return size or None
    except (requests.RequestException, ValueError):
        return None


def fetch(src: Source, dest_dir: Path, attempts: int = 200, stall_seconds: int = 30, echo=print) -> Path:
    dest = dest_dir / src.file
    total = _remote_size(src.url)
    if dest.exists() and total and dest.stat().st_size >= total:
        echo(f"  ✓ {src.file} já baixado ({dest.stat().st_size / 1e6:.0f} MB)")
        return dest
    for attempt in range(1, attempts + 1):
        have = dest.stat().st_size if dest.exists() else 0
        headers = {"User-Agent": UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with requests.get(src.url, headers=headers, stream=True, timeout=(15, stall_seconds)) as r:
                if r.status_code == 416:  # já temos tudo
                    break
                if have and r.status_code == 200:  # servidor ignorou o Range: recomeça do zero
                    have = 0
                r.raise_for_status()
                mode = "ab" if have else "wb"
                with open(dest, mode) as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            break  # terminou sem erro
        except (requests.RequestException, OSError) as e:
            size = dest.stat().st_size if dest.exists() else 0
            if attempt % 5 == 1:
                echo(f"  … {src.file}: {size / 1e6:.0f} MB (conexão caiu: {type(e).__name__}; retomando)")
            time.sleep(min(10, 2 + attempt // 5))
    size = dest.stat().st_size if dest.exists() else 0
    if total and size < total and not src.allow_truncated:
        raise RuntimeError(f"{src.file} incompleto ({size} de {total} bytes) — rode de novo para retomar")
    echo(f"  ✓ {src.file} ({size / 1e6:.0f} MB){' — ' + src.note if src.note else ''}")
    return dest


def download_all(dest_dir: Path, only: list[str] | None = None, echo=print) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in SOURCES:
        if only and not any(o in src.file for o in only):
            continue
        echo(f"→ {src.file}")
        fetch(src, dest_dir, echo=echo)
