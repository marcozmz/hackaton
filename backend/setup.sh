#!/usr/bin/env bash
# Plant+Facil — instalação no Linux/Mac (ou Git Bash).
# Uso (dentro de backend/):
#   ./setup.sh                          # só instala
#   ./setup.sh plantefacil-db.zip       # instala + banco pronto
set -euo pipefail
cd "$(dirname "$0")"
DB="${1:-}"

echo "== 1/4 Python"
PY=$(command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "Python não encontrado. Instale o Python 3.10+."; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Use Python 3.10+."; exit 1; }
"$PY" --version

echo "== 2/4 Ambiente virtual e dependências"
[ -d .venv ] || "$PY" -m venv .venv
if [ -x .venv/bin/python ]; then BIN=.venv/bin; else BIN=.venv/Scripts; fi
"$BIN/python" -m pip install -q --upgrade pip
"$BIN/pip" install -q -r requirements.txt

echo "== 3/4 Configuração (.env)"
if [ ! -f .env ]; then cp .env.example .env; echo "   .env criado (IA opcional: LLM_API_KEY)."; else echo "   .env já existe."; fi

echo "== 4/4 Banco de dados"
export FLASK_APP=run.py
if [ -z "$DB" ]; then for c in plantefacil-db.zip ../plantefacil-db.zip; do [ -f "$c" ] && DB="$c" && break; done; fi
if [ -n "$DB" ]; then
  echo "   Restaurando banco pronto de $DB"
  "$BIN/flask" data import-db --file "$DB"
  "$BIN/flask" db upgrade
else
  "$BIN/flask" db upgrade
  echo
  echo "   Banco criado VAZIO. Escolha:"
  echo "   (a) rápido: $BIN/flask data import-db --file CAMINHO/plantefacil-db.zip"
  echo "   (b) do zero (~1,5 GB do MAPA, 30-60 min): $BIN/flask data bootstrap"
fi

echo
echo "Pronto! Rode: $BIN/flask --app run.py run --debug   e abra http://127.0.0.1:5000"
