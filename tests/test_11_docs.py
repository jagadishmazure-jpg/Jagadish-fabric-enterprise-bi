"""Documentation tests: excerpts are real, outputs are current, component docs are complete."""

import re
import subprocess
import sys

import pytest

from fabricbi.paths import DOCS_DIR, ROOT

EXCERPT = re.compile(r"<!-- excerpt: (\S+) -->\n```\w*\n(.*?)```", re.S)
COMPONENT_DOCS = [
    "domain.md",
    "cold-path.md",
    "hot-path.md",
    "lambda-view.md",
    "enrichment.md",
    "semantic-model.md",
    "data-agent.md",
    "agent-interfaces.md",
    "governance.md",
    "observability.md",
    "finops.md",
    "kql.md",
    "fabric-items.md",
    "infrastructure.md",
    "deployment.md",
]
REQUIRED_SECTIONS = ["## Architecture", "## How it works", "## Key files", "## Run it locally", "## Tests", "## Failure modes", "## On real Fabric", "## Limitations"]


def _md():
    skip = {".venv", ".git", ".terraform"}
    return [p for p in ROOT.rglob("*.md") if not (set(p.relative_to(ROOT).parts) & skip)]


def test_every_component_doc_exists_and_is_indexed():
    index = (DOCS_DIR / "README.md").read_text()
    for name in COMPONENT_DOCS:
        assert (DOCS_DIR / name).exists(), name
        assert f"({name})" in index, f"{name} missing from docs/README.md"


@pytest.mark.parametrize("name", COMPONENT_DOCS)
def test_component_doc_has_required_sections(name):
    text = (DOCS_DIR / name).read_text()
    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    assert missing == [], f"{name} lacks {missing}"
    assert "<!-- example:" in text or "## Run it locally" in text


def test_code_excerpts_are_copied_from_the_source():
    problems, n = [], 0
    for doc in _md():
        for path, body in EXCERPT.findall(doc.read_text()):
            n += 1
            src = ROOT / path
            if not src.exists():
                problems.append(f"{doc.relative_to(ROOT)}: {path} does not exist")
                continue
            source_lines = [ln.strip() for ln in src.read_text().splitlines()]
            want = [ln.strip() for ln in body.splitlines() if ln.strip() and ln.strip() != "..."]
            text = "\n".join(source_lines)
            # the excerpt's lines must appear in the source, in order (a "..." line marks a gap)
            pos = 0
            for ln in want:
                found = text.find(ln, pos)
                if found < 0:
                    problems.append(f"{doc.relative_to(ROOT)}: line not in {path}: {ln!r}")
                    break
                pos = found + len(ln)
    assert n >= 15
    assert problems == []


def test_example_outputs_and_test_counts_are_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "doc_outputs.py"), "--check"], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_placeholders_left():
    bad = re.compile(r"\b(TODO|TBD|FIXME|lorem ipsum)\b|coming soon", re.I)
    hits = [f"{p.relative_to(ROOT)}: {m.group(0)}" for p in _md() for m in bad.finditer(p.read_text())]
    assert hits == []


def test_implementation_guide_has_verification_for_every_step():
    text = (DOCS_DIR / "implementation-guide.md").read_text()
    steps = re.findall(r"^### Step \d+", text, re.M)
    assert len(steps) >= 10
    for block in re.split(r"^### Step \d+", text, flags=re.M)[1:]:
        assert "**Verify:**" in block
