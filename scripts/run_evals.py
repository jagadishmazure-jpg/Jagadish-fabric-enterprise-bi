"""Run the full pipeline on synthetic data, then every eval gate. Exit 1 on any regression.

python scripts/run_evals.py                    # gate + evals-out/eval-report.json
python scripts/run_evals.py --update-baseline  # also refresh evals/baseline.json (agent card score)"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fabricbi import evals  # noqa: E402
from fabricbi.pipeline import run_all  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evals-out")
    ap.add_argument("--update-baseline", action="store_true")
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        run = run_all(Path(tmp))
        report = evals.run_all(run)
    evals.write_report(report, ROOT / a.out)
    for section, r in report.items():
        flat = {k: v for k, v in r.items() if not isinstance(v, list | dict)}
        print(f"{section:<11} {flat}")
    failures = evals.gate(report)
    base_path = ROOT / "evals" / "baseline.json"
    if a.update_baseline:
        base_path.write_text(json.dumps(evals.flatten(report), indent=1, sort_keys=True) + "\n")
    elif base_path.exists():
        failures += evals.regressions(report, json.loads(base_path.read_text()))
    if failures:
        print("EVAL GATE FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("eval gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
