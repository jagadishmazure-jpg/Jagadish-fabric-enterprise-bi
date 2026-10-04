# `modules/storage`

ADLS Gen2 landing account (hierarchical namespace, TLS 1.2, shared keys off, no public blobs), a landing container, Blob Data Contributor for the ingest identity and Blob Data Reader for readers such as Purview.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`main.tf`](main.tf) | Resources |
| [`outputs.tf`](outputs.tf) | Values returned to the root stack |
| [`variables.tf`](variables.tf) | Inputs with types, defaults and validation |
| [`versions.tf`](versions.tf) | Provider constraints |
