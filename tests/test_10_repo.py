"""Repository checks: generated files current, Fabric items well formed, eval gates, hygiene."""

import json
import re
import subprocess
import sys
import uuid

import pytest

from fabricbi import evals
from fabricbi.paths import FABRIC_DIR, ROOT

SKIP_DIRS = {
    ".git",
    ".venv",
    ".terraform",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "evals-out",
    "build",
    "dist",
}


def _tracked():
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    files = (
        [ROOT / f for f in out.stdout.splitlines()]
        if out.returncode == 0 and out.stdout
        else [p for p in ROOT.rglob("*") if p.is_file()]
    )
    return [
        f
        for f in files
        if f.exists() and not (set(f.relative_to(ROOT).parts) & SKIP_DIRS) and ".egg-info" not in str(f)
    ]


def _is_fabric_item(d):
    rel = d.relative_to(ROOT).parts
    return len(rel) >= 3 and rel[:2] == ("fabric", "workspace")


@pytest.mark.parametrize("script", ["export_contracts.py", "cost_report.py", "model_card.py"])
def test_generated_files_are_current(script):
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--check"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_fabric_items_have_valid_platform_files():
    items = sorted(p.parent for p in FABRIC_DIR.rglob(".platform"))
    assert len(items) == 7
    ids = []
    for d in items:
        meta = json.loads((d / ".platform").read_text())
        name, kind = d.name.rsplit(".", 1)
        assert meta["metadata"]["type"] == kind and meta["metadata"]["displayName"] == name
        ids.append(str(uuid.UUID(meta["config"]["logicalId"])))
    assert len(set(ids)) == len(ids)


def test_notebooks_are_fabric_python_notebooks():
    for nb in FABRIC_DIR.rglob("notebook-content.py"):
        text = nb.read_text()
        assert text.startswith("# Fabric notebook source")
        compile(re.sub(r"^%.*$", "", text, flags=re.M), str(nb), "exec")


def test_parameter_file_covers_both_environments():
    import yaml

    spec = yaml.safe_load((FABRIC_DIR / "workspace" / "parameter.yml").read_text())
    text = json.dumps(spec)
    assert "dev" in text and "prod" in text


def test_eval_gate_passes(run, tmp_path):
    report = evals.run_all(run)
    assert evals.gate(report) == []
    evals.write_report(report, tmp_path)
    assert any(tmp_path.iterdir())


def test_eval_gate_fails_below_floor():
    report = {"nl2sql": {"nl2sql_execution_accuracy": 0.5}, "catalog": {"catalog_findings": 2}}
    failures = evals.gate(report)
    assert any(f.startswith("nl2sql_execution_accuracy") for f in failures)
    assert any(f.startswith("catalog_findings") for f in failures)


def test_baseline_regression_is_detected():
    base = json.loads((ROOT / "evals" / "baseline.json").read_text())
    same = {"all": dict(base)}
    assert evals.regressions(same, base) == []
    worse = {
        "all": {
            **base,
            "retrieval_hit_at_3": base["retrieval_hit_at_3"] - 0.1,
            "wape_model": base["wape_model"] + 0.1,
        }
    }
    assert len(evals.regressions(worse, base)) == 2


def test_agent_card_eval_score_matches_baseline():
    card = json.loads((ROOT / "control-plane" / "agent-card.json").read_text())
    base = json.loads((ROOT / "evals" / "baseline.json").read_text())
    assert card["capabilities"]["extensions"][0]["params"]["eval_score"] == base["nl2sql_execution_accuracy"]


def test_every_folder_readme_lists_its_files():
    problems = []
    for d in sorted({f.parent for f in _tracked()}):
        if d == ROOT or _is_fabric_item(d):
            continue
        readme = d / "README.md"
        if not readme.exists():
            problems.append(f"{d.relative_to(ROOT)} has no README.md")
            continue
        text = readme.read_text()
        if "| File | What it does |" not in text:
            problems.append(f"{readme.relative_to(ROOT)} has no file table")
        for child in sorted(d.iterdir()):
            if (
                child.name in SKIP_DIRS
                or (child.name.startswith(".") and child.name not in (".terraform.lock.hcl", ".tflint.hcl"))
                or ".egg-info" in child.name
            ):
                continue
            if f"`{child.name}`" not in text and f"`{child.name}/`" not in text:
                problems.append(f"{readme.relative_to(ROOT)} does not list {child.name}")
    assert problems == []


DATE = re.compile(
    r"\b(199\d|20[0-3]\d)\b|\b(January|February|March|April|June|July|August|September|October|November|December)\b|\bMay \d"
)


def test_no_dates_in_docs():
    hits = [
        f"{f.relative_to(ROOT)}: {m.group(0)}"
        for f in _tracked()
        if f.suffix == ".md" and f.name not in ("CHANGELOG.md",)
        for m in DATE.finditer(f.read_text())
    ]
    assert hits == []


def test_no_real_client_names_and_fictional_company_only():
    banned = re.compile("mei" + "jer", re.I)  # split so this file does not match itself
    hits = [
        str(f.relative_to(ROOT))
        for f in _tracked()
        if f.suffix in (".md", ".py", ".yaml", ".yml", ".json", ".kql", ".tf", ".bicep")
        and banned.search(f.read_text(errors="ignore"))
    ]
    assert hits == []


def test_no_reference_material_committed():
    assert not (ROOT / "refs").exists()
    assert not any(f.relative_to(ROOT).parts[0] == "refs" for f in _tracked())


def test_adrs_are_indexed_and_undated():
    adr = ROOT / "docs" / "adr"
    files = sorted(p.name for p in adr.glob("0*.md"))
    assert len(files) == 6
    index = (adr / "README.md").read_text()
    for name in files:
        assert name in index
        assert "**Date:**" not in (adr / name).read_text()


def test_markdown_links_resolve():
    broken = []
    for f in _tracked():
        if f.suffix != ".md":
            continue
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", f.read_text()):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (f.parent / target).exists():
                broken.append(f"{f.relative_to(ROOT)} -> {target}")
    assert broken == []


def test_workflows_gate_deploy_and_use_oidc():
    import yaml

    wf = ROOT / ".github" / "workflows"
    deploy = yaml.safe_load((wf / "deploy.yml").read_text())
    for name, job in deploy["jobs"].items():
        if name != "preflight":
            assert "vars.DEPLOY_ENABLED == 'true'" in job["if"]
            assert job["permissions"]["id-token"] == "write"
    assert deploy["jobs"]["deploy-prod"]["environment"] == "prod"
    text = "".join(p.read_text() for p in wf.glob("*.yml"))
    assert "client-secret" not in text and "AZURE_CLIENT_SECRET" not in text
    teardown = yaml.safe_load((wf / "teardown.yml").read_text())
    assert "inputs.confirm == inputs.environment" in teardown["jobs"]["teardown"]["if"]
