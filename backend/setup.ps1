# Plant+Facil — instalação no Windows.
# Uso (dentro de backend\):
#   powershell -ExecutionPolicy Bypass -File setup.ps1                       # só instala
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Db plantefacil-db.zip  # instala + banco pronto
param([string]$Db = "")

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/4 Python"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "Python não encontrado. Instale o Python 3.10+ (python.org) marcando 'Add to PATH'." }
$ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$ver -lt [version]"3.10") { throw "Python $ver é antigo demais; use 3.10 ou mais novo." }
Write-Host "   Python $ver"

Write-Host "== 2/4 Ambiente virtual e dependências (pode levar alguns minutos)"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python -m pip install -q --upgrade pip
& .\.venv\Scripts\pip install -q -r requirements.txt

Write-Host "== 3/4 Configuração (.env)"
if (-not (Test-Path ".env")) {
  Copy-Item .env.example .env
  Write-Host "   .env criado a partir do .env.example (a IA é opcional: coloque LLM_API_KEY se tiver)."
} else { Write-Host "   .env já existe (mantido)." }

Write-Host "== 4/4 Banco de dados"
$env:FLASK_APP = "run.py"
if ($Db -eq "") {
  foreach ($c in @("plantefacil-db.zip", "..\plantefacil-db.zip")) { if (Test-Path $c) { $Db = $c; break } }
}
if ($Db -ne "") {
  Write-Host "   Restaurando banco pronto de $Db"
  & .\.venv\Scripts\flask data import-db --file $Db
  & .\.venv\Scripts\flask db upgrade
} else {
  & .\.venv\Scripts\flask db upgrade
  Write-Host ""
  Write-Host "   Banco criado VAZIO. Escolha um caminho:"
  Write-Host "   (a) rápido: peça o plantefacil-db.zip para a equipe e rode:"
  Write-Host "       .\.venv\Scripts\flask data import-db --file CAMINHO\plantefacil-db.zip"
  Write-Host "   (b) do zero (baixa ~1,5 GB do portal do MAPA; 30-60 min):"
  Write-Host "       .\.venv\Scripts\flask data bootstrap"
}

Write-Host ""
Write-Host "Pronto! Para rodar:"
Write-Host "   .\.venv\Scripts\flask --app run.py run --debug"
Write-Host "   e abra http://127.0.0.1:5000"
