# ADR 0002: Local Parquet and DuckDB as the OneLake stand-in

- **Status:** Accepted

## Context

The logic worth reviewing in a lakehouse (idempotent ingest, contracts, quarantine, CDC apply,
star schema keys, row-level security, guardrails on generated SQL) does not need a Fabric
capacity to run. Requiring one would make every test run cost money and need a tenant, and most
readers of this repo have neither.

## Decision

Run everything offline by default. Tables are Parquet files under `lh_retail/Tables/` with the
same `<layer>__<table>` names the Fabric notebooks write; DuckDB plays the SQL analytics endpoint;
SQLite plays the operational database being mirrored; a seeded generator replaces real sources;
the Foundry model is a deterministic mock. The Fabric notebooks in `fabric/workspace/` implement
the same transformations in PySpark for the real platform.

## Consequences

- The full pipeline, the seven eval gates and 200 tests run in seconds on a laptop or CI runner with no
  credentials.
- Two implementations of the medallion logic exist (pandas here, PySpark in the notebooks). The
  contracts in `contracts/schemas/` are the shared definition of the output, but the notebooks
  have not been executed on Fabric, so parity is by design, not proven.
- DuckDB SQL and Fabric T-SQL differ. The data agent's SQL is parsed with sqlglot, which can
  transpile, but the generated dialect has only been executed against DuckDB.
