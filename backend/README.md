# Plante Fácil — Backend

1ª Hackathon de Dados Abertos · IFSP Araraquara (02–03/10/2026). Visão do produto: [`../readme.md`](../readme.md).

Plataforma de apoio à decisão para a agricultura familiar: transforma dados públicos
(ZARC – Tábua de Risco e ZARC – Cultivares, do MAPA) em uma orientação simples:
**"para este lugar, esta cultura e este solo, quando plantar e com qual risco?"**

> A IA explica; as regras decidem; os dados oficiais sustentam.

Flask 3 · SQLAlchemy 2 · SQLite (Postgres depois) · Pydantic v2 · pandas (só na importação).
Arquitetura detalhada em `files/` (fora do repositório).

### 1. Instalar

```bash
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
flask data import-sisser --file ../arquivos/dados_abertos_psr_2025_sisser.xlsx   # seguro rural (agregado)
flask data import-malhas                          # limites municipais IBGE p/ o mapa (~3 MB, instance/geo)
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
| `GET /api/v1/weather/outlook?place=Araraquara SP` | previsão de 7 dias já interpretada (Open-Meteo) |
| `GET /api/v1/recommendations/planting/simple?…` | mesma consulta, texto reescrito por IA (sob demanda) |
| `GET /api/v1/insurance/summary?place=Rio Verde GO&crop=milho` | seguro rural (PSR) agregado da região |
| `GET /api/v1/geo/municipalities/{ibge}` | ponto (centroide) + limite do município (GeoJSON) |
| `GET /api/v1/geo/layers/zarc-risk?uf=SP&crop=milho&soil=2` | camada do estado: situação de plantio de hoje por município |
| `GET /api/v1/geo/legend` | legenda semântica do mapa |
| `GET /api/v1/sources` | fontes, licenças, versões e data de extração |

Parâmetros úteis da recomendação: `level=simple|standard|technical`, `date=AAAA-MM-DD`
(simular outra data), `debug=1` (só em desenvolvimento: zonas ZARC cruas).

### Previsão do tempo (desejável, implementada)

- Provider em `WEATHER_PROVIDER`: `open_meteo` (padrão, sem chave), `fixture` (resposta gravada, para demo sem internet) ou `none`.
- Cada consulta vira um `forecast_run` válido por 3 h por município (cache); se o Open-Meteo cair,
  usa o último run de até 24 h (`forecast.status = degraded`) ou segue só com o ZARC (`unavailable`, confiança −0,20).
- Regras: chuva forte ≥ 50 mm/dia nos próximos 5 dias (atenção), chuva moderada ≥ 30 mm (informativo),
  pouca chuva em 7 dias dentro da janela (atenção: esperar umidade) ou boa umidade (ok).
  Limiares **provisórios** (referência: avisos do INMET) em `app/domain/engine/thresholds.py`.
- A previsão **nunca cria janela de plantio**: só ajusta o "quando, dentro da janela" e avisa riscos.

### Seguro rural — SISSER/PSR (desejável, implementado)

- A planilha oficial **contém dados pessoais** (nome e documento do segurado, coordenadas, nº de apólice).
  O importador lê **só colunas não pessoais** (`SAFE_COLUMNS` em `app/ingestion/sisser.py`) e grava
  apenas **agregados por município × cultura × ano**. Nenhuma linha individual entra no banco ou no log.
- **k-anonimato (k = 3):** município com menos de 3 apólices da cultura não é exibido; a resposta sobe
  para o agregado do estado (ou para o total do município, todas as culturas).
- Bloco `insurance` + ação "pergunte sobre o seguro rural: para ter direito à subvenção, plante dentro do ZARC".
  É **informativo**: nunca altera o risco. A base aberta não traz sinistros (indenização vem vazia).
- Várias planilhas (uma por ano, 2016–2025) podem ser passadas com `--file` repetido.

### Mapa (desejável, implementado)

- **Backend prepara o significado; frontend desenha** (Leaflet ou similar; tiles de terceiros, ex.: OpenStreetMap com atribuição).
- Limites municipais do IBGE (`qualidade=minima`, já simplificados) em arquivos estáticos por UF — sem PostGIS.
- Camada `zarc-risk`: para cada município da UF, a situação **hoje** com a mesma lógica da recomendação
  (solo conservador, ciclos em união, sequeiro): `low | medium | high | out_of_window | no_data` + texto pronto.
  **Sem cores e sem códigos do ZARC** na resposta: o frontend mapeia `level` → cor usando `legend`.
- Cache de 6 h por UF × cultura × solo × decêndio; respostas com gzip (SP ≈ 77 KB).

### IA para simplificar o texto (desejável, implementado)

> A IA explica; as regras decidem; os dados oficiais sustentam.

- **Gemini** (`gemini-3.5-flash-lite`, cota gratuita do Google AI Studio, ~1–5 s) ou **Ollama** local
  (`LLM_PROVIDER=ollama`). Sem `LLM_API_KEY` → só templates (o produto funciona igual).
- A IA recebe só o **contexto estruturado já decidido** (cultura, município, decisão, janela, motivos, ações,
  previsão, seguro) — sem coordenadas, IDs ou dados pessoais — e só **reescreve**.
- **Guard** (`app/domain/narrative/guard.py`): todo número e mês do texto precisa existir no contexto;
  proíbe promessas ("garantido", "sem risco"), agrotóxicos, links e markdown; máx. 700 caracteres.
  Reprovou, deu timeout ou estourou a cota → **texto do template** (`generated_by: "template"` + motivo).
- Nunca no caminho crítico: `/recommendations/planting` não chama IA; o texto simplificado é outro endpoint
  (botão "explicar de forma mais simples"), com cache de 24 h e limite de 10/min.
- No Jinja: `SimplifyService().simplify(rec, level)` com o `rec` de `RecommendationService().planting_advice(...)`.

### Contas, perfil e assistente (ADR-17)

- Páginas Jinja em `../templates`, blueprint `web` (`app/web/`) chamando os services.
- Contas: senha com hash scrypt, sessão em cookie assinado, CSRF em todo POST (`app/security/auth.py`),
  limite de 10 tentativas/min no login e cadastro. Só guardamos nome de tratamento, e-mail e dados da roça.
- LGPD: consentimento no cadastro, `GET /perfil/meus-dados` (download) e `POST /perfil/excluir` (apaga tudo).
- Assistente (`POST /assistente/mensagem`): regras escolhem a ferramenta (recomendação, previsão,
  cultivares, seguro, glossário em `app/seeds/glossary.yaml`); a IA só reescreve, com guard.
  Pragas/defensivos → recusa e indica a ATER. O servidor não guarda conversas.

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

Nenhum dado pessoal é coletado ou gravado no MVP (o SISSER entra só agregado, com k-anonimato): município, cultura e solo vêm na consulta
e só existem no cache da recomendação. Ver `files/09-security.md`.
