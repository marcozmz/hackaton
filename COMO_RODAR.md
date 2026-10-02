# Como rodar o Plant+Facil na sua máquina

Backend (Flask) e frontend (páginas Jinja em `templates/`) rodam **juntos, num único servidor**.

## Pré-requisitos

- **Python 3.10 ou mais novo** ([python.org](https://www.python.org/downloads/) — no Windows, marque *Add python.exe to PATH*)
- **Git**
- O arquivo **`plantefacil-db.zip`** (~56 MB): o banco já pronto com os dados oficiais.
  Peça para quem tem (link no grupo). Sem ele dá para montar do zero, mas demora (veja o fim).

## Passo a passo

```bash
git clone https://github.com/marcozmz/hackaton.git
cd hackaton
git checkout main          # ou a branch combinada com a equipe
cd backend
```

Coloque o `plantefacil-db.zip` dentro de `backend/` e rode o instalador:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
.\.venv\Scripts\flask --app run.py run --debug
```

**Linux / Mac / Git Bash:**
```bash
chmod +x setup.sh && ./setup.sh
.venv/bin/flask --app run.py run --debug
```

Abra **http://127.0.0.1:5000** 🌱

O instalador: cria o ambiente virtual, instala as dependências, cria o `.env` a partir do
`.env.example` e restaura o banco do zip (se ele estiver em `backend/` ou na pasta acima).

## Páginas

| Endereço | O que é |
|---|---|
| `/` | Consulta: onde, o quê, tipo de terra |
| `/clima?place=Chapecó SC&crop=feijão&soil=3` | Resultado: semáforo do ZARC, janela, previsão, cultivares, avisos, seguro, mapa |
| `/assistente`, `/perfil`, `/login`, `/cadastro` | Protótipos (funcionalidades futuras) |
| `/api/v1/...` | API JSON (ver `backend/README.md`) |

## IA (opcional)

Sem chave, tudo funciona com textos prontos. Para o botão "Explicar de um jeito mais simples" usar IA,
coloque no `backend/.env` a chave do Google AI Studio: `LLM_API_KEY=...`
**Nunca commite o `.env`** (ele já está no `.gitignore`).

## Mostrar no celular (mesma rede Wi-Fi)

```bash
flask --app run.py run --host 0.0.0.0
```
e abra `http://IP-DO-COMPUTADOR:5000` no celular. (O GPS do navegador só funciona em `localhost`
ou HTTPS; pelo IP, digite o município.)

## Testes

```bash
.venv/Scripts/python -m pytest      # Windows
.venv/bin/python -m pytest          # Linux/Mac
```

## Sem o zip: montar o banco do zero

Baixa ~1,5 GB do portal do MAPA (lento, cai às vezes — o comando retoma sozinho) e importa tudo:

```bash
flask --app run.py data bootstrap     # 30–60 min
```

Para gerar um novo zip para a equipe: `flask --app run.py data prune` e depois
`flask --app run.py data export-db --out plantefacil-db.zip`.

## Problemas comuns

| Sintoma | Solução |
|---|---|
| `python` não encontrado | Reinstale o Python marcando *Add to PATH* |
| Script do PowerShell bloqueado | Use exatamente `powershell -ExecutionPolicy Bypass -File setup.ps1` |
| "Sem zoneamento oficial" para tudo | Banco vazio: restaure o zip (`flask data import-db --file ...`) |
| Previsão "indisponível" | Sem internet ou Open-Meteo fora; para demo offline: `WEATHER_PROVIDER=fixture` no `.env` |
| Porta 5000 ocupada | `flask --app run.py run --port 5001` |
