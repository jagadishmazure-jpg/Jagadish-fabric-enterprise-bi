"""Write docs/cost-estimate.md from finops/workloads.yaml (ESTIMATES ONLY), or --check it is current."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fabricbi.finops.capacity import markdown, size  # noqa: E402

TARGET = ROOT / "docs" / "cost-estimate.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    text = markdown(size())
    if a.check:
        if not TARGET.exists() or TARGET.read_text() != text:
            print("docs/cost-estimate.md is stale; run python scripts/cost_report.py")
            return 1
        print("cost estimate current")
        return 0
    TARGET.write_text(text)
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
