# Model card: demand forecast

| Field | Value |
|---|---|
| Model | scikit-learn `GradientBoostingRegressor` |
| Task | net sales per store and category, 7 days ahead |
| Owner | commercial-analytics (catalog asset `ml.demand_forecast`) |
| Training data | `gold.agg_daily_sales`, synthetic (fictional Fernhill Grocers) |
| Status | trained and evaluated offline; not registered or deployed |

## Intended use

Planning input for store replenishment and staffing: a number per store, category and day that a
planner can compare with their own judgement. It is not meant for automatic ordering, and it has
never seen real sales.

## Features

All features are known 7 days before the target day, so the backtest does not leak
the future: `lag7`, `lag14`, `lag21`, `mean7_lag7`, `dow`, `store_key`, `cat_code`, `square_meters`.

Hyperparameters: `{'n_estimators': 250, 'max_depth': 3, 'learning_rate': 0.05, 'subsample': 0.9, 'random_state': 0}`.

## Evaluation

Backtest on the last 14 days, 1,176 store-category-days (trained on
1,764). Metric: weighted absolute percentage error (WAPE, lower is better).

| Model | WAPE |
|---|---:|
| Seasonal naive (same weekday last week) | 0.3933 |
| Gradient boosting | 0.3125 |

Improvement over the baseline: **20.5%**. The eval gate fails the build if the model does not
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
