# PLANTE FÁCIL — VISÃO DO PRODUTO

## 1. O que é o Plante Fácil

O **Plante Fácil** é uma plataforma de inteligência e apoio à decisão para agricultores, com foco inicial na **agricultura familiar**, que transforma dados agrícolas públicos e dados climáticos em **orientações simples, contextualizadas e acionáveis**.

O objetivo não é simplesmente mostrar dados ao agricultor.

O objetivo é responder, de forma clara:

> **"Considerando onde estou, o que quero plantar, as características da minha região, o solo, o clima e os dados agrícolas disponíveis, o que eu deveria saber e fazer para reduzir os riscos da minha produção?"**

A plataforma deve funcionar como uma camada de interpretação entre os dados públicos e o agricultor.

Em vez de obrigar o usuário a interpretar CSVs, mapas, tabelas, termos técnicos e diferentes fontes governamentais, o Plante Fácil organiza essas informações e transforma os dados em contexto e orientação.

---

# 2. Problema que queremos resolver

Existem diversas bases públicas com informações extremamente relevantes para a agricultura, mas essas informações estão espalhadas em diferentes fontes, formatos e níveis de complexidade.

Um agricultor pode precisar considerar simultaneamente:

* localização da propriedade;
* município;
* cultura que deseja plantar;
* tipo de solo;
* janela de plantio;
* risco climático;
* previsão meteorológica;
* histórico climático;
* cultivares indicadas;
* características da região;
* possibilidade de proteção/seguro rural;
* informações técnicas relacionadas à cultura.

O problema é que esses dados normalmente não estão organizados para responder diretamente à pergunta do agricultor.

O Plante Fácil deve fazer essa integração.

### Exemplo

Em vez de mostrar apenas:

> Zarc: determinada cultura possui uma janela de plantio entre determinadas datas.

O sistema deve conseguir transformar isso em algo como:

> **🌽 Você está dentro da região X e deseja plantar milho.**
>
> Para as condições selecionadas, o período indicado pelo Zarc começa em **X** e termina em **Y**.
>
> O nível de risco é **X**.
>
> A previsão para os próximos dias indica **X**.
>
> **Recomendação:** aguarde/realize o plantio dentro da janela indicada e acompanhe as condições climáticas.

A informação técnica continua existindo, mas o sistema apresenta primeiro aquilo que é útil para a tomada de decisão.

---

# 3. Público-alvo

O público principal é o **agricultor familiar**, mas o sistema não deve ser limitado a um único nível de conhecimento.

Existem usuários com diferentes níveis de familiaridade com tecnologia e agricultura.

Por isso, o produto deve possuir uma camada de apresentação capaz de atender desde:

### Usuário com pouca familiaridade técnica

Deve receber:

* frases curtas;
* linguagem simples;
* recomendações diretas;
* alertas claros;
* explicação de termos técnicos;
* possibilidade de ouvir a orientação em áudio.

Exemplo:

> ⚠️ **Atenção**
>
> A previsão indica chuva forte nos próximos dias.
>
> Se você ainda não plantou, confira a janela recomendada antes de começar.

### Usuário mais experiente

Pode acessar:

* dados utilizados;
* mapas;
* gráficos;
* histórico;
* nível de risco;
* fontes;
* justificativas;
* informações técnicas;
* parâmetros utilizados pelo sistema.

Portanto, o sistema deve possuir **diferentes níveis de profundidade da mesma informação**, sem criar dois produtos diferentes.

---

# 4. Princípio central do produto

O princípio mais importante do Plante Fácil é:

> **Complexidade nos bastidores. Simplicidade na experiência do agricultor.**

O usuário não deve precisar entender como diferentes bases de dados foram cruzadas.

O backend deve realizar essa complexidade e entregar ao frontend informações estruturadas.

A cadeia conceitual é:

```text
LOCALIZAÇÃO
      ↓
CULTURA
      ↓
SOLO
      ↓
ZARC
      ↓
CLIMA ATUAL
      ↓
PREVISÃO
      ↓
HISTÓRICO
      ↓
DADOS AGRÍCOLAS
      ↓
REGRAS / CONHECIMENTO TÉCNICO
      ↓
MOTOR DE DECISÃO
      ↓
RECOMENDAÇÃO
      ↓
LINGUAGEM SIMPLES
      ↓
AGRICULTOR
```

A IA pode participar da última etapa e de outras funções, mas **não deve simplesmente inventar recomendações a partir de um prompt**.

---

# 5. Dados e fontes prioritárias

O projeto deve priorizar dados públicos e oficiais.

A principal base pivô do projeto é:

## Zarc — Tábua de Risco

O Zarc é o principal elemento da primeira versão porque permite trabalhar com:

* cultura;
* município;
* tipo de solo;
* períodos de plantio;
* risco.

Ele deve ser o núcleo da primeira decisão do sistema.

A pergunta principal inicialmente será:

> **"Para esta localização, cultura e condição de solo, quando e em quais condições o plantio é indicado?"**

---

## Zarc — Cultivares

A base de cultivares complementa o Zarc.

Quando houver informação disponível, o sistema poderá relacionar:

```text
Cultura
   ↓
Região/Zona
   ↓
Condição de solo
   ↓
Cultivares indicadas
```

Isso permite que a recomendação seja mais específica.

---

## SISSER

O SISSER será utilizado como uma camada relacionada à **proteção e gestão de risco da produção**.

A ideia não é fazer dele o núcleo agronômico da decisão.

Ele pode complementar a informação mostrando contexto relacionado ao seguro rural.

O sistema deve ser capaz de trabalhar tanto com dados recentes quanto, se viável no MVP, com histórico.

Para o histórico, os dados podem ser organizados por ano:

```text
SISSER
├── 2016
├── 2017
├── ...
├── 2024
└── 2025
```

Porém, devido ao limite de tempo do hackathon, o histórico não deve comprometer o desenvolvimento do fluxo principal.

---

## Base de Conhecimento / informações técnicas

Bases oficiais de conhecimento agrícola podem ser utilizadas para complementar as recomendações e explicações.

A intenção é aproximar:

```text
DADO TÉCNICO
     ↓
INTERPRETAÇÃO
     ↓
ORIENTAÇÃO PRÁTICA
```

---

## Thesagro

O Thesagro pode ser utilizado futuramente para auxiliar na organização de termos e vocabulário agrícola.

Entretanto, ele não deve ser tratado como dependência obrigatória do MVP.

O produto precisa funcionar mesmo sem ele.

---

# 6. Linguagem regional e sinônimos

Um problema importante do produto é que o mesmo elemento agrícola pode possuir diferentes nomes dependendo da região.

Por exemplo:

```text
Mandioca
├── aipim
├── macaxeira
└── outros nomes regionais
```

O sistema não deve espalhar essas equivalências pelo código.

Deve existir uma camada estruturada de vocabulário:

```text
Cultura oficial
      ↓
Aliases / nomes populares
      ↓
Região
      ↓
Nome apresentado ao usuário
```

Isso permite que o usuário pesquise utilizando o termo que conhece, enquanto o sistema trabalha internamente com uma identificação padronizada.

Exemplo:

```text
Usuário:
"Quero plantar aipim"

Sistema:
"aipim" → mandioca → cultura oficial correspondente
```

Essa normalização deve ser responsabilidade do backend/domínio, e não do frontend.

---

# 7. Localização como contexto

A localização é uma das principais entradas do sistema.

O usuário pode informar:

* município;
* estado;
* localização geográfica;
* futuramente GPS/localização da propriedade.

A localização deve permitir buscar e relacionar informações como:

```text
Localização
    ↓
Município
    ↓
Estado
    ↓
Região agrícola
    ↓
Dados Zarc
    ↓
Clima
    ↓
Solo
    ↓
Histórico
    ↓
Recomendações
```

A localização não deve ser apenas um ponto exibido em um mapa.

Ela é um **contexto para o motor de decisão**.

---

# 8. Mapas

O mapa é uma ferramenta de visualização.

O backend deve preparar os dados geográficos necessários, mas o frontend deve ser responsável pela renderização e interação do mapa.

### Backend

Deve fornecer:

* coordenadas;
* GeoJSON quando apropriado;
* polígonos;
* pontos;
* limites;
* camadas;
* propriedades dos elementos;
* filtros;
* dados necessários para consulta espacial.

### Frontend

Deve cuidar de:

* renderizar o mapa;
* zoom;
* seleção;
* filtros visuais;
* marcadores;
* cores/camadas;
* interação do usuário.

A regra é:

> **Backend prepara o significado e os dados geográficos. Frontend apresenta o mapa.**

---

# 9. Motor de decisão

O principal diferencial técnico do Plante Fácil deve ser o **motor de decisão**.

Ele deve combinar diferentes informações antes de produzir uma recomendação.

Exemplo conceitual:

```text
Localização
+
Cultura
+
Solo
+
Zarc
+
Previsão climática
+
Histórico
+
Conhecimento técnico
+
Regras
=
Contexto agrícola
```

A partir desse contexto:

```text
Contexto agrícola
       ↓
Análise de risco
       ↓
Regras de decisão
       ↓
Recomendação
```

Uma recomendação não deve ser apenas:

```text
"Plante agora."
```

Ela deve possuir contexto.

Por exemplo:

```json
{
  "tipo": "plantio",
  "nivel_risco": "baixo",
  "recomendacao": "Iniciar o plantio dentro da janela indicada.",
  "motivos": [
    "...",
    "..."
  ],
  "periodo": {
    "inicio": "...",
    "fim": "..."
  },
  "fontes": [
    "Zarc"
  ],
  "confianca": "...",
  "gerado_em": "..."
}
```

A estrutura exata deve ser definida na arquitetura.

---

# 10. Explicabilidade

O agricultor deve conseguir entender **por que** recebeu determinada orientação.

Sempre que possível, uma recomendação deve permitir responder:

* O que foi recomendado?
* Por quê?
* Quais dados foram considerados?
* Qual período foi analisado?
* Qual fonte forneceu os dados?
* Qual é o nível de confiança?
* Qual ação o usuário deve tomar?

Isso é importante tanto para a confiança do usuário quanto para a apresentação do projeto.

---

# 11. Papel da Inteligência Artificial

A IA é uma camada de inteligência e comunicação, não a única fonte de verdade do sistema.

A arquitetura desejada é:

```text
DADOS OFICIAIS
      ↓
NORMALIZAÇÃO
      ↓
REGRAS / MOTOR DE DECISÃO
      ↓
CONTEXTO ESTRUTURADO
      ↓
IA
      ↓
LINGUAGEM NATURAL
```

A IA pode:

* transformar informações técnicas em linguagem simples;
* gerar resumos;
* explicar recomendações;
* responder perguntas;
* adaptar a profundidade da explicação ao usuário;
* futuramente atuar como chatbot;
* gerar conteúdo em áudio.

A IA não deve:

* inventar dados;
* inventar fontes;
* substituir dados oficiais;
* ignorar as regras do sistema;
* fornecer uma recomendação agronômica sem base nos dados disponíveis.

Quando uma informação não estiver disponível, o sistema deve conseguir deixar isso explícito.

---

# 12. Chatbot futuro

O produto deve ser preparado para futuramente possuir um chatbot agrícola.

O chatbot não deve funcionar como um modelo isolado.

Ele deverá consultar o contexto estruturado do Plante Fácil.

Exemplo:

> Usuário: "Posso plantar milho agora?"

O fluxo desejado é:

```text
Pergunta
   ↓
Identificação da cultura
   ↓
Identificação da localização
   ↓
Contexto do usuário
   ↓
Consulta às bases
   ↓
Motor de decisão
   ↓
Resposta estruturada
   ↓
IA transforma em linguagem natural
```

Assim o chatbot utiliza os mesmos dados e regras da aplicação principal.

---

# 13. Áudio

Como parte da acessibilidade, o sistema poderá transformar recomendações em áudio.

Fluxo:

```text
Recomendação estruturada
        ↓
Resumo em linguagem simples
        ↓
TTS
        ↓
Arquivo de áudio
        ↓
Armazenamento
        ↓
URL/ID
        ↓
Frontend
        ↓
Reprodução
```

O backend deverá ser responsável pela geração/gestão do áudio.

O frontend apenas reproduz o arquivo.

Essa funcionalidade pode ser assíncrona e possuir cache para evitar gerar o mesmo áudio repetidamente.

---

# 14. Alertas

O sistema deve futuramente conseguir gerar alertas relacionados ao contexto agrícola.

Exemplos conceituais:

* alteração relevante na previsão;
* aproximação de período de risco;
* início/fim de janela de plantio;
* condição climática relevante;
* necessidade de atenção relacionada à cultura.

Os alertas devem ser baseados em dados e regras, e não simplesmente em texto gerado por IA.

---

# 15. Arquitetura do produto

O backend será o **motor de inteligência e decisão**.

O frontend será principalmente a **camada de experiência e visualização**.

### Backend

Responsável por:

* autenticação;
* usuários;
* propriedades;
* localização;
* culturas;
* solos;
* ingestão de dados;
* normalização;
* aliases;
* integração com APIs;
* processamento de dados;
* cruzamento de dados;
* regras;
* motor de decisão;
* cálculo de risco;
* recomendações;
* alertas;
* IA;
* geração de resumo;
* geração de áudio;
* dados para mapas;
* histórico;
* cache;
* tarefas assíncronas;
* rastreabilidade;
* fontes.

### Frontend

Responsável por:

* interface;
* navegação;
* formulários;
* cards;
* dashboards;
* gráficos;
* mapas;
* filtros;
* apresentação das recomendações;
* interação do usuário;
* reprodução de áudio.

O frontend não deve duplicar regras agrícolas importantes que já existem no backend.

---

# 16. Experiência desejada

A experiência principal deve ser extremamente simples.

Um fluxo inicial possível:

```text
1. Onde você está?
        ↓
2. O que deseja plantar?
        ↓
3. Qual é o tipo de solo?
        ↓
4. Analisar
        ↓
5. Resultado
```

O resultado deve apresentar primeiro a resposta prática.

Por exemplo:

```text
🌱 MILHO

📍 Araraquara - SP

🟢 Condição favorável

📅 Janela indicada:
10/10/2026 → 20/12/2026

🌧️ Previsão:
...

🌾 Cultivares:
...

⚠️ Atenção:
...

💡 O que fazer agora:
...
```

Depois o usuário pode expandir:

```text
Por que recebi essa recomendação?
```

e acessar os dados técnicos e fontes.

---

# 17. Transparência dos dados

Toda informação relevante deve possuir rastreabilidade.

O sistema deve saber:

```text
Recomendação
    ↓
Regra utilizada
    ↓
Dados utilizados
    ↓
Dataset
    ↓
Fonte
    ↓
Data de coleta
    ↓
Período de validade
```

Isso é especialmente importante porque os dados agrícolas podem ser atualizados.

O sistema não deve tratar dados externos como eternamente válidos.

---

# 18. Escopo do MVP do hackathon

O projeto será desenvolvido dentro de um hackathon de aproximadamente 27 horas.

Portanto, o objetivo não é construir uma plataforma agrícola completa.

O objetivo é construir um **protótipo funcional que demonstre claramente o conceito e o valor do produto**.

### MVP essencial

```text
Localização
    ↓
Cultura
    ↓
Solo
    ↓
Zarc
    ↓
Janela de plantio
    ↓
Risco
    ↓
Cultivares
    ↓
Recomendação simples
```

### MVP desejável

Adicionar:

```text
Previsão climática
SISSER
Mapa
Explicação da recomendação
IA para simplificação do texto
```

### Futuro

Deixar arquitetura preparada para:

* chatbot;
* áudio;
* histórico agrícola;
* alertas;
* propriedades;
* múltiplas culturas;
* dados históricos;
* mais bases públicas;
* recomendações mais avançadas;
* análises geoespaciais;
* integração com novas fontes;
* expansão para diferentes regiões.

---

# 19. O que NÃO queremos

Não queremos construir simplesmente:

* um aplicativo de previsão do tempo;
* um dashboard cheio de gráficos;
* um visualizador de CSVs;
* um mapa bonito sem função;
* um chatbot que responde sem consultar dados;
* uma IA que inventa recomendações;
* um sistema extremamente complexo impossível de demonstrar no hackathon.

O valor está em **transformar dados públicos dispersos em uma decisão compreensível para o agricultor**.

---

# 20. Visão final

A ideia central do Plante Fácil pode ser resumida como:

```text
DADOS ABERTOS
      +
LOCALIZAÇÃO
      +
CULTURA
      +
SOLO
      +
CLIMA
      +
ZARC
      +
CONHECIMENTO AGRÍCOLA
      +
REGRAS
      +
IA
      ↓
PLANTE FÁCIL
      ↓
INFORMAÇÃO AGRÍCOLA CONTEXTUALIZADA
      ↓
RECOMENDAÇÃO SIMPLES E ACIONÁVEL
```

O produto deve responder à pergunta que realmente importa para o agricultor:

> **"O que eu preciso saber e fazer agora para tomar uma decisão melhor sobre minha produção?"**

A arquitetura, o banco de dados e as APIs devem ser construídos a partir dessa visão de produto, e não o contrário.