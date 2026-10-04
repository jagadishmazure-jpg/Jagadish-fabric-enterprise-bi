"""Keep the real command output pasted in the docs current.

A doc marks an output block like this (the command is shown in a bash block just above it):

    <!-- example: hotpath -->
    ```text
    ...output of `python -m fabricbi.examples hotpath`...
    ```

    python scripts/doc_outputs.py           # rewrite every marked block from a fresh run
    python scripts/doc_outputs.py --check   # exit 1 if any block is stale (CI)

The check also compares every "N automated tests" / "N tests" claim in the Markdown with the
number pytest actually collects."""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fabricbi import examples  # noqa: E402

BLOCK = re.compile(r"(<!-- example: (\w+) -->\n```text\n)(.*?)(```)", re.S)
CLAIM = re.compile(r"\*\*(\d[\d,]*) automated tests\*\*|pytest -q +# (\d[\d,]*) tests")
SKIP = {".venv", ".git", ".terraform", "node_modules"}


def md_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.md") if not (set(p.relative_to(ROOT).parts) & SKIP)]


def output_of(name: str, cache: dict) -> str:
    if name not in cache:
        if name not in examples.EXAMPLES:
            raise SystemExit(f"unknown example {name!r}")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            examples.EXAMPLES[name]()
        cache[name] = buf.getvalue()
    return cache[name]


def collected_tests() -> int:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True
    )
    m = re.search(r"(\d+) tests? collected", r.stdout)
    if not m:
        raise SystemExit("could not count tests:\n" + r.stdout[-500:] + r.stderr[-500:])
    return int(m.group(1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    cache: dict[str, str] = {}
    stale, blocks = [], 0
    for p in md_files():
        text = p.read_text()

        def repl(m: re.Match) -> str:
            return m.group(1) + output_of(m.group(2), cache) + m.group(4)

        new, n = BLOCK.subn(repl, text)
        blocks += n
        if new != text:
            stale.append(p.relative_to(ROOT))
            if not a.check:
                p.write_text(new)
    n_tests = collected_tests()
    wrong = []
    for p in md_files():
        for m in CLAIM.finditer(p.read_text()):
            claimed = int((m.group(1) or m.group(2)).replace(",", ""))
            if claimed != n_tests:
                wrong.append(f"{p.relative_to(ROOT)} claims {claimed} tests, pytest collects {n_tests}")
    if a.check and stale:
        print(
            "stale example output in:\n  "
            + "\n  ".join(map(str, stale))
            + "\nrun: python scripts/doc_outputs.py"
        )
    if wrong:
        print("\n".join(wrong))
    if (a.check and stale) or wrong:
        return 1
    print(
        f"{blocks} example blocks {'current' if a.check else 'written'}; test count {n_tests} matches the docs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
