# Plante Fácil

- Hackaton 02/10/2026 — 1ª Hackathon de Dados Abertos · IFSP Araraquara

Plataforma de apoio à decisão para a agricultura familiar: transforma dados públicos
(ZARC – Tábua de Risco e ZARC – Cultivares, do MAPA) em uma orientação simples:
**"para este lugar, esta cultura e este solo, quando plantar e com qual risco?"**

> A IA explica; as regras decidem; os dados oficiais sustentam.

## Backend (`backend/`)

Flask 3 · SQLAlchemy 2 · SQLite (Postgres depois) · Pydantic v2 · pandas (só na importação).
Arquitetura detalhada em `files/` (fora do repositório).

### 1. Instalar

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Linux/Mac: .venv/bin/pip
cp .env.example .env
```

### 2. Baixar as bases oficiais (não versionadas — são grandes)

Coloque em uma pasta (ex.: `../arquivos/`):

| Base | Origem |
|---|---|
| `dados-abertos-tabua-de-risco-safra-2026-2027.csv` | [ZARC – Tábua de Risco](https://dados.agricultura.gov.br/dataset/tabua-de-risco-zoneamento-agricola-de-risco-climatico) (MAPA, CC-BY) |
| `dados-abertos-tabua-de-risco-safra-perene-olericola-sem-safra.csv` | idem (contém mandioca) |
| `siszarc_cronograma.csv.gz` | [ZARC – Cultivares](https://dados.agricultura.gov.br/dataset/siszarc-sistemas-de-zoneamento-agricola-e-risco-climatico) (MAPA, CC-BY) |
| `municipios.csv`, `estados.csv` | [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (IBGE, MIT) |

> O portal do MAPA recusa clientes sem *user-agent* de navegador e derruba conexões longas:
> use `curl -A "Mozilla/5.0" -L -C - -o arquivo URL` e repita até terminar (o `-C -` retoma).

### 3. Criar o banco e importar

```bash
export FLASK_APP=run.py
flask db upgrade
flask data seed                                   # fontes, solos, culturas e nomes regionais
flask data import-municipios --municipios ../arquivos/ibge_municipios.csv --estados ../arquivos/ibge_estados.csv
flask data import-zarc --file ../arquivos/tabua-de-risco-safra-2026-2027.csv \
                       --file ../arquivos/tabua-de-risco-perene-olericola-sem-safra.csv
# Cultivares: o arquivo oficial tem >140 M linhas (≈1 GB .gz) e costuma vir truncado.
# Reduza às linhas distintas da safra e importe o arquivo pequeno:
python scripts/extract_cultivares.py ../arquivos/siszarc_cronograma.csv.gz ../arquivos/cultivares_2026-2027.csv.gz --season 2026-2027
flask data import-zarc-cultivares --file ../arquivos/cultivares_2026-2027.csv.gz --season 2026-2027
flask data list-versions
```

Cada importação é **versionada** (`dataset_version`), **idempotente** (hash dos arquivos)
e só troca a versão vigente no fim, numa transação. Falhou? A versão anterior continua valendo.
Só ficam no banco as culturas do MVP e os decêndios com risco aceitável (formato longo).

Para inspecionar um arquivo grande sem abri-lo inteiro:
`python scripts/inspect_dataset.py ARQUIVO --values Nome_cultura`

### 4. Rodar

```bash
flask run            # http://127.0.0.1:5000/api/v1/health
pytest               # testes (domínio puro + API com mini-ZARC sintético)
```

### API (MVP essencial)

| Rota | O que faz |
|---|---|
| `GET /api/v1/health` | status + versão do ZARC carregada |
| `GET /api/v1/location/resolve?q=Araraquara SP` · `?cep=` · `?lat=&lon=` | lugar → município IBGE |
| `GET /api/v1/location/municipalities?q=arar&uf=SP` | autocomplete |
| `GET /api/v1/crops?q=aipim` | nome regional → cultura oficial (`match` ou `candidates`) |
| `GET /api/v1/crops/{slug}` · `/crops/{slug}/varieties?municipality=` | ficha e cultivares indicadas |
| `GET /api/v1/soils` | 3 opções simples de solo (+ "não sei") |
| `GET /api/v1/recommendations/planting?place=Araraquara SP&crop=milho&soil=2` | **recomendação de janela de plantio** |
| `GET /api/v1/sources` | fontes, licenças, versões e data de extração |

Parâmetros úteis da recomendação: `level=simple|standard|technical`, `date=AAAA-MM-DD`
(simular outra data), `debug=1` (só em desenvolvimento: zonas ZARC cruas).

### Como a recomendação é decidida

1. **Localização** → município (código IBGE). **Cultura** → nome oficial (aliases: aipim, macaxeira…).
2. **ZARC**: zonas do município × cultura × solo, só **sequeiro** por padrão.
   - Solo não informado (ou várias classes no mesmo grupo, ou níveis de manejo da soja):
     **janela conservadora** (vale em todos, com o maior risco).
   - Ciclos e safras diferentes (ex.: milho 1ª e 2ª safra): **união** (opções para o agricultor).
3. **Regras** (`app/domain/engine/rules/`): dentro/fora da janela, risco 20/30/40% → baixo/médio/alto,
   janela acabando, período de menor risco, cultivares, lacunas.
4. **Risco = pior achado** (nunca média). **Sem zoneamento = `no_data`**, nunca "risco alto".
5. **Narrator** transforma códigos em texto simples (`app/domain/narrative/messages/pt_BR.yaml`).
6. Toda resposta traz **motivo, fontes (com data de extração), confiança (com o que reduziu) e validade**.

### Privacidade

Nenhum dado pessoal é coletado ou gravado no MVP: município, cultura e solo vêm na consulta
e só existem no cache da recomendação. Ver `files/09-security.md`.
