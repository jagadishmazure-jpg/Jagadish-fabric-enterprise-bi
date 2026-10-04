# `fabricbi.coldpath`

Batch path into the local Lakehouse ([cold-path.md](../../../docs/cold-path.md)).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`__init__.py`](__init__.py) | Package marker |
| [`lakehouse.py`](lakehouse.py) | OneLake stand-in: Parquet tables, metadata, shortcuts |
| [`bronze.py`](bronze.py) | Idempotent landing and bronze load |
| [`mirroring.py`](mirroring.py) | Operational DB change log and a checkpointed mirror replica |
| [`contracts.py`](contracts.py) | Schema contract validation and compatibility |
| [`quality.py`](quality.py) | Rules, quarantine and the DQ gate |
| [`silver.py`](silver.py) | Typing, dedup, quarantine, PII redaction |
| [`gold.py`](gold.py) | Star schema and daily aggregate |
