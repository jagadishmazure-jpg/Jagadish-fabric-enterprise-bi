# Architecture

The build follows the shape most Fabric analytics estates converge on: land everything in one
lake, keep a fast path for what is happening now and a careful path for what happened, and put
one governed serving layer in front of people and agents. Inspired by Microsoft's Fabric
enterprise BI reference patterns; the design, names and code here are my own.

This page is the overview. Each component has its own page (see the [docs index](README.md)), and
the [implementation guide](implementation-guide.md) walks through running and deploying it.

## End to end

```mermaid
flowchart LR
  subgraph SRC[Source systems]
    POS[POS export<br/>CSV]
    CAT[Product catalog<br/>JSON]
    FZH[Freezer history<br/>CSV]
    TIX[Support tickets<br/>free text]
    OPDB[(Operational DB<br/>stores, members)]
    EVH[[Event Hubs<br/>live checkouts]]
    IOT[[IoT Hub<br/>freezer sensors]]
  end
  subgraph ING[Ingest]
    COPY[Copy jobs / pipelines<br/>bronze.py]
    MIR[Mirroring<br/>mirroring.py]
    ES[Eventstream<br/>stream.py]
  end
  subgraph ONE[OneLake]
    LH[(Lakehouse<br/>bronze / silver / gold)]
    MR[(Mirrored replica)]
    EH[(Eventhouse<br/>windows + alerts)]
    SC{{Shortcuts}}
  end
  subgraph PRC[Process]
    NB[Spark notebooks<br/>silver.py, gold.py]
    KQL[KQL querysets<br/>kql/*.kql]
  end
  subgraph ENR[Enrich]
    ML[Demand forecast<br/>scikit-learn]
    FDY[Foundry classifier<br/>mocked]
  end
  subgraph SRV[Serve]
    SM[Semantic model<br/>Direct Lake, TMDL]
    LAM[Lambda view<br/>batch + speed]
    DA[Data agent<br/>NL to SQL + guardrails]
    VS[Vector store<br/>docs and contracts]
    MCP[MCP server]
    A2A[A2A agent card]
  end
  USERS[Analysts · store managers<br/>agents · AI apps · partners]
  POS & CAT & FZH & TIX --> COPY --> LH
  OPDB --> MIR --> MR -.shortcut.-> SC -.-> LH
  EVH & IOT --> ES --> EH
  LH --> NB --> LH
  EH --> KQL --> EH
  LH --> ML & FDY --> LH
  LH --> SM & DA
  LH & EH --> LAM
  VS --> MCP
  DA --> MCP & A2A
  SM & LAM & MCP & A2A --> USERS
  GOV[[Purview-style governance<br/>catalog · lineage · labels · RLS/OLS · contracts]]
  GOV -.-> ONE
  GOV -.-> SRV
```

## Two speeds, one serving view (Lambda)

| Path | Latency | What it is good at | Code |
|---|---|---|---|
| Hot (speed layer) | seconds to minutes | live tiles, alerts, "how is today going" | [`hotpath/`](../src/fabricbi/hotpath), [`kql/`](../kql) |
| Cold (batch layer) | once a day | corrected, conformed history; the star schema; ML features | [`coldpath/`](../src/fabricbi/coldpath) |
| Serving | on read | one table that shows batch history and today's partial numbers without double counting | [`lambda_view.py`](../src/fabricbi/lambda_view.py) |

```mermaid
flowchart LR
  G[gold.agg_daily_sales<br/>days before the cut-off] --> U{{union at the cut-off}}
  H[hot-path windows<br/>events after the cut-off] --> U
  U --> V[gold.serving_sales_daily<br/>source = batch or speed]
  N[next batch load] -.moves the cut-off, batch replaces speed.-> U
```

## Medallion layers

```mermaid
flowchart LR
  L[Files/landing<br/>exact copy + manifest] --> B[bronze<br/>all text, ingest metadata]
  B --> S[silver<br/>typed · de-duplicated · quality rules<br/>quarantine · PII redacted]
  S --> G[gold<br/>star schema · aggregates · forecasts]
  Q[(silver.*_quarantine)]
  S -.rejected rows + rule.-> Q
```

| Layer | Contract | Who reads it |
|---|---|---|
| bronze | none beyond ingest metadata; kept for replay | data engineers |
| silver | YAML schema contracts on `pos_lines` and `products`; quality rules on every table, with a 2% quarantine gate | data engineers, data scientists |
| gold | a schema contract on every table, checked before each write | the semantic model, the data agent, ML, partners |

## Gold model (star schema)

```mermaid
erDiagram
  fact_sales }o--|| dim_store : store_key
  fact_sales }o--|| dim_product : product_key
  fact_sales }o--|| dim_customer : customer_key
  fact_sales }o--|| dim_date : date_key
  fact_freezer_daily }o--|| dim_store : store_key
  fact_freezer_daily }o--|| dim_date : date_key
  fact_ticket }o--|| dim_store : store_key
  fact_ticket }o--|| dim_date : date_key
```

## Mapping to Fabric and Azure items

| Concept | Fabric / Azure item | Offline stand-in |
|---|---|---|
| Streaming ingest | Event Hubs, IoT Hub, Fabric Eventstream | `hotpath.stream.simulate` |
| Real-time store | Eventhouse (KQL database) | Parquet under `eh_retail/` + `hotpath.windows` |
| Batch ingest | Data Factory pipelines, copy job | `coldpath.bronze.BronzeIngest` |
| Database replication | Fabric Mirroring | `coldpath.mirroring` on SQLite |
| Lake storage | OneLake Lakehouse (Delta) | Parquet under `lh_retail/Tables` |
| Shortcuts | OneLake internal and external shortcuts | `Lakehouse.add_shortcut` |
| Transform | Spark notebooks, T-SQL, Dataflow Gen2 | pandas in `silver.py` and `gold.py`; Fabric notebook items in [`fabric/`](../fabric) |
| ML | Fabric data science or Azure ML | scikit-learn in `enrich/forecast.py` |
| LLM enrichment | Microsoft Foundry model deployment | `enrich/foundry_mock.py` |
| BI | Power BI semantic model in Direct Lake mode | YAML + generated TMDL in [`semantic-model/`](../semantic-model) |
| Conversational analytics | Fabric data agent | `serve/data_agent.py` |
| Agent interfaces | MCP server, A2A | `serve/mcp_server.py`, `serve/a2a.py` |
| Governance | Microsoft Purview | `governance/` |
| Monitoring | Azure Monitor, Log Analytics, App Insights | `observability/`, [`kql/monitoring`](../kql/monitoring) |
