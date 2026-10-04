.PHONY: install lint test evals demo contracts cost card bicep terraform secrets overlap check
install:          ## venv + dev extras
	python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
lint:
	ruff check . && ruff format --check .
test:             ## all tests, offline
	pytest -q
evals:            ## run the pipeline, then every eval gate (exit 1 on regression)
	python scripts/run_evals.py
demo:             ## end-to-end demo, including MCP over stdio and A2A over HTTP
	python scripts/demo.py
contracts:        ## regenerate agent card, MCP tools, TMDL and the KQL database schema
	python scripts/export_contracts.py
cost:             ## regenerate docs/cost-estimate.md (estimates)
	python scripts/cost_report.py
card:             ## regenerate the forecast model card from a real run
	python scripts/model_card.py
bicep:            ## compile the Bicep (never deploys)
	bicep build infra/main.bicep --stdout > /dev/null
terraform:        ## offline: fmt, validate and plan tests with mocked providers
	cd infra/terraform && terraform fmt -check -recursive && terraform init -backend=false -input=false >/dev/null && terraform validate && terraform test
secrets:
	python scripts/secrets_scan.py
overlap:          ## originality check against local reference files (never committed)
	python scripts/overlap_check.py $(REFS)
check:            ## what CI runs (Python side)
	ruff check . && ruff format --check . && python scripts/export_contracts.py --check && python scripts/cost_report.py --check && python scripts/model_card.py --check && python scripts/secrets_scan.py && pytest -q && python scripts/run_evals.py && python scripts/demo.py
