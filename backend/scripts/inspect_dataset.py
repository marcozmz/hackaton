"""Inspeciona um CSV/XLSX grande sem carregá-lo inteiro.

Imprime apenas: encoding, separador, colunas, tipos, contagem de linhas
(opcional) e poucas linhas de amostra truncadas. Nunca despeja o arquivo.

Uso:
    python scripts/inspect_dataset.py ARQUIVO [--sample 3] [--count]
        [--values COLUNA ...] [--sheet NOME]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import sys
from pathlib import Path

import pandas as pd

ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")
MAX_CELL = 40


def _open_text(path: Path, encoding: str):
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding=encoding, newline="")
    return open(path, encoding=encoding, newline="")


def detect(path: Path) -> tuple[str, str]:
    for enc in ENCODINGS:
        try:
            with _open_text(path, enc) as fh:
                head = fh.read(64_000)
            sep = csv.Sniffer().sniff(head.splitlines()[0], delimiters=";,\t|").delimiter
            return enc, sep
        except (UnicodeDecodeError, csv.Error):
            continue
    raise SystemExit("não consegui detectar encoding/separador")


def trunc(v) -> str:
    s = str(v)
    return s if len(s) <= MAX_CELL else s[: MAX_CELL - 1] + "…"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--sample", type=int, default=3)
    ap.add_argument("--count", action="store_true", help="conta linhas (lê em chunks)")
    ap.add_argument("--values", nargs="*", default=[], help="colunas p/ listar valores distintos (máx 40)")
    ap.add_argument("--sheet", default=None)
    a = ap.parse_args()
    p: Path = a.path
    print(f"arquivo: {p.name}  ({p.stat().st_size / 1e6:.1f} MB)")

    if p.suffix in (".xlsx", ".xls"):
        xl = pd.ExcelFile(p)
        print("abas:", xl.sheet_names)
        df = xl.parse(a.sheet or xl.sheet_names[0], nrows=max(a.sample, 200))
        reader = None
    else:
        enc, sep = detect(p)
        print(f"encoding: {enc}  separador: {sep!r}")
        opts = dict(sep=sep, encoding=enc, dtype=str, low_memory=False)
        df = pd.read_csv(p, nrows=max(a.sample, 200), **opts)
        reader = lambda: pd.read_csv(p, chunksize=200_000, usecols=a.values or None, **opts)  # noqa: E731

    print(f"colunas ({len(df.columns)}):")
    for c in df.columns:
        print(f"  - {c}  ex: {trunc(df[c].dropna().iloc[0]) if df[c].notna().any() else '∅'}")
    print("amostra:")
    for _, row in df.head(a.sample).iterrows():
        print("  ", {k: trunc(v) for k, v in row.items() if pd.notna(v)})

    if reader and (a.count or a.values):
        total, distinct = 0, {c: {} for c in a.values}
        for chunk in reader():
            total += len(chunk)
            for c in a.values:
                for k, n in chunk[c].value_counts().items():
                    distinct[c][k] = distinct[c].get(k, 0) + n
        print(f"linhas: {total}")
        for c, d in distinct.items():
            items = sorted(d.items(), key=lambda kv: -kv[1])
            print(f"valores de {c} ({len(items)} distintos):")
            for k, n in items[:40]:
                print(f"   {trunc(k)}: {n}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
