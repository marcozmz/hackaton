"""Reduz o arquivo oficial ZARC – Cultivares (~1 GB .gz, >140 M linhas) às linhas distintas de uma safra.

O arquivo repete a mesma cultivar milhares de vezes (por isso é enorme) e o portal do MAPA
costuma entregá-lo truncado. Este script lê em streaming até onde o gzip permitir, filtra a(s)
safra(s) pedida(s), remove duplicatas e grava um CSV pequeno no mesmo formato — que então
é importado com `flask data import-zarc-cultivares --file <saida>`.

Uso:
    python scripts/extract_cultivares.py ENTRADA.csv.gz SAIDA.csv.gz --season 2026-2027
"""
from __future__ import annotations

import argparse
import gzip
import sys

import pandas as pd

COLS = ["Safra", "Cultura", "Obtentor_Mantenedor", "Cultivar", "UF", "Grupo", "Regiao_de_Adaptacao"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--season", action="append", required=True)
    a = ap.parse_args()

    parts, read, truncated = [], 0, False
    try:
        with gzip.open(a.src, "rt", encoding="utf-8-sig") as fh:
            for ch in pd.read_csv(fh, sep=";", dtype=str, usecols=COLS, chunksize=1_000_000):
                read += len(ch)
                sel = ch[ch.Safra.isin(a.season)].drop_duplicates()
                if not sel.empty:
                    parts.append(sel)
    except (EOFError, gzip.BadGzipFile, pd.errors.ParserError) as e:
        truncated = True
        print(f"aviso: arquivo terminou antes do fim ({type(e).__name__}); usando o que foi lido")

    out = pd.concat(parts).drop_duplicates() if parts else pd.DataFrame(columns=COLS)
    with gzip.open(a.dst, "wt", encoding="utf-8") as fh:
        out.to_csv(fh, sep=";", index=False)
    print(f"lidas={read} distintas={len(out)} truncado={truncated} → {a.dst}")
    print("culturas:", out.Cultura.nunique(), "· UFs:", out.UF.nunique())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
