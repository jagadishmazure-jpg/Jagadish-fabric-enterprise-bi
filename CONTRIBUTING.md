# Contributing

This is a portfolio repository, but issues and pull requests are welcome. The bar for a change is the same one CI enforces.

## Set up

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
```

## Checks to run before a pull request

```bash
make check        # everything below in one go
ruff check . && ruff format --check .
pytest -q                                   # includes the repo hygiene checks
python scripts/run_evals.py                 # eval gate
python scripts/export_contracts.py --check  # agent card, MCP tools, TMDL, KQL schema
python scripts/cost_report.py --check && python scripts/model_card.py --check
python scripts/demo.py                      # end-to-end run
```

Infrastructure (offline, no Azure login needed):

```bash
terraform -chdir=infra/terraform init -backend=false && terraform -chdir=infra/terraform validate && terraform -chdir=infra/terraform test
bicep build infra/main.bicep --stdout > /dev/null
```

## Conventions

- Keep everything runnable offline: new code needs a mock or synthetic data and a test that uses it.
- Use only synthetic data for the fictional Fernhill Grocers. Never commit real customer data, keys, connection strings or `.tfstate` files.
- A new table needs a schema contract, a catalog entry with an owner and label, and lineage recorded by the step that writes it; the catalog check fails otherwise.
- A change to a KQL constant needs the same change in `fabricbi.hotpath.windows` (a test compares them).
- Every folder has a `README.md` with a `| File | What it does |` table (Fabric item folders excepted, since Fabric publishes their contents); add a row when you add a file.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `ci:`, `build:`, `test:`).
- Infrastructure changes go into both Bicep and Terraform.
- Docs describe what the code does today. Mark anything else as planned. Numbers must come from a real run.
- Record significant design choices as an ADR in [`docs/adr/`](docs/adr/README.md) and add a line to [`CHANGELOG.md`](CHANGELOG.md).
