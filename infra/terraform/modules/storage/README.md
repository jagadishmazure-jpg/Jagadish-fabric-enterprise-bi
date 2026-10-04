# `modules/storage`

ADLS Gen2 landing account (hierarchical namespace, TLS 1.2, shared keys off, no public blobs), the landing and partner-share containers, Storage Blob Data Reader for readers (the ingest identity, Purview) and an optional Storage Blob Data Contributor list (empty in the root stack).

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`main.tf`](main.tf) | Storage account, containers and data-plane role assignments |
| [`outputs.tf`](outputs.tf) | Values returned to the root stack |
| [`variables.tf`](variables.tf) | Inputs with types, defaults and validation |
| [`versions.tf`](versions.tf) | Provider constraints |
