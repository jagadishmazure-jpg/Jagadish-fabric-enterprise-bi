# `contracts`

Machine-checked promises about data: schema contracts per table and data product contracts per team.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`schemas/`](schemas/) | One YAML contract per silver and gold table: columns, types, keys, nullability, ranges |
| [`products/`](products/) | Data product contracts: owner, output ports, sensitivity, SLOs, consumers, sharing |

Guides: [cold-path.md](../docs/cold-path.md) (schema contracts) and [governance.md](../docs/governance.md) (data products).
