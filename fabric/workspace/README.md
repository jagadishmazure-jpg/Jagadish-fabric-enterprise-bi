# `fabric/workspace`

One folder per Fabric item (`<name>.<ItemType>` with a `.platform` file). Item folders hold only what Fabric expects, so they have no README of their own; this table describes them.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`lh_retail.Lakehouse/`](lh_retail.Lakehouse/) | Lakehouse with schemas; bronze, silver and gold tables live here |
| [`eh_retail.Eventhouse/`](eh_retail.Eventhouse/) | Eventhouse for the hot path |
| [`kqldb_retail.KQLDatabase/`](kqldb_retail.KQLDatabase/) | KQL database; `DatabaseSchema.kql` is generated from `kql/tables.kql` |
| [`nb_bronze_ingest.Notebook/`](nb_bronze_ingest.Notebook/) | PySpark: landing files to bronze tables with load metadata |
| [`nb_silver.Notebook/`](nb_silver.Notebook/) | PySpark: typing, dedup, quarantine, redaction |
| [`nb_gold.Notebook/`](nb_gold.Notebook/) | PySpark: star schema and daily aggregate |
| [`sm_retail_sales.SemanticModel/`](sm_retail_sales.SemanticModel/) | Direct Lake semantic model; TMDL generated from `semantic-model/retail_sales.yaml` |
| [`parameter.yml`](parameter.yml) | fabric-cicd find-and-replace values per environment |
