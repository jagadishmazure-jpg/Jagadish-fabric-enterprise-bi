"""Write docs/model-card-demand-forecast.md from a real training run, or --check it matches."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fabricbi.enrich.forecast import FEATURES, HOLDOUT_DAYS, HORIZON_DAYS, MODEL_PARAMS  # noqa: E402
from fabricbi.pipeline import run_all  # noqa: E402

TARGET = ROOT / "docs" / "model-card-demand-forecast.md"


def render(res) -> str:
    imp = res.improvement
    return f"""# Model card: demand forecast

| Field | Value |
|---|---|
| Model | scikit-learn `GradientBoostingRegressor` |
| Task | net sales per store and category, {HORIZON_DAYS} days ahead |
| Owner | commercial-analytics (catalog asset `ml.demand_forecast`) |
| Training data | `gold.agg_daily_sales`, synthetic (fictional Fernhill Grocers) |
| Status | trained and evaluated offline; not registered or deployed |

## Intended use

Planning input for store replenishment and staffing: a number per store, category and day that a
planner can compare with their own judgement. It is not meant for automatic ordering, and it has
never seen real sales.

## Features

All features are known {HORIZON_DAYS} days before the target day, so the backtest does not leak
the future: {", ".join(f"`{f}`" for f in FEATURES)}.

Hyperparameters: `{MODEL_PARAMS}`.

## Evaluation

Backtest on the last {HOLDOUT_DAYS} days, {res.rows_test:,} store-category-days (trained on
{res.rows_train:,}). Metric: weighted absolute percentage error (WAPE, lower is better).

| Model | WAPE |
|---|---:|
| Seasonal naive (same weekday last week) | {res.wape_naive:.4f} |
| Gradient boosting | {res.wape_model:.4f} |

Improvement over the baseline: **{imp:.1%}**. The eval gate fails the build if the model does not
beat the baseline.

## Limitations

- Synthetic data with a simple weekly pattern and a mild trend; real demand has promotions,
  holidays, weather and stock-outs that are not modelled.
- No prediction intervals yet; planners see a point forecast only.
- No drift monitoring yet. Planned: compare live WAPE by week against this card and alert when it
  degrades past the naive baseline.

## Responsible use

No personal data is used (the aggregate has no customer keys). Forecasts are shared with a
supplier partner through the `demand-forecast` data product, labelled General.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        text = render(run_all(Path(tmp)).forecast)
    if a.check:
        if not TARGET.exists() or TARGET.read_text() != text:
            print("model card is stale; run python scripts/model_card.py")
            return 1
        print("model card current")
        return 0
    TARGET.write_text(text)
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
