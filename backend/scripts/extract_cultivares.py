"""Reduz o arquivo oficial ZARC – Cultivares às linhas distintas de uma safra.

Uso (dentro de backend/):
    python scripts/extract_cultivares.py ENTRADA.csv.gz SAIDA.csv.gz --season 2026-2027
(O `flask data bootstrap` já faz isso sozinho.)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ingestion.zarc_cultivars import extract_distinct  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--season", action="append", required=True)
    a = ap.parse_args()
    r = extract_distinct(a.src, a.dst, a.season)
    print(f"lidas={r['read']} distintas={r['distinct']} truncado={r['truncated']} → {a.dst}")
