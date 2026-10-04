"""Seven-day-ahead demand forecast per store and category.

In Fabric this is a Spark notebook that trains with scikit-learn and logs to an ML experiment, or
an Azure ML job that reads the gold table through a OneLake shortcut. Here it is plain
scikit-learn on the gold aggregate.

Every feature is known seven days before the target day (lags of 7, 14 and 21 days, a 7-day
mean ending a week earlier, weekday, store size, category), so the backtest is honest about what
the model would have known. The model has to beat the seasonal naive baseline (same weekday last
week) on the hold-out weeks, or `ForecastResult.passed` is False and the eval gate fails."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

HORIZON_DAYS = 7
HOLDOUT_DAYS = 14
FEATURES = ["lag7", "lag14", "lag21", "mean7_lag7", "dow", "store_key", "cat_code", "square_meters"]
MODEL_PARAMS = {
    "n_estimators": 250,
    "max_depth": 3,
    "learning_rate": 0.05,
    "subsample": 0.9,
    "random_state": 0,
}


@dataclass
class ForecastResult:
    wape_model: float
    wape_naive: float
    rows_train: int
    rows_test: int
    model: GradientBoostingRegressor
    predictions: pd.DataFrame

    @property
    def improvement(self) -> float:
        return 1 - self.wape_model / self.wape_naive

    @property
    def passed(self) -> bool:
        return self.wape_model < self.wape_naive


def wape(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.abs(actual - pred).sum() / max(np.abs(actual).sum(), 1e-9))


def features(agg: pd.DataFrame, dim_store: pd.DataFrame) -> pd.DataFrame:
    agg = agg.assign(date=pd.to_datetime(agg.date_key.astype(str), format="%Y%m%d"))
    cats = sorted(agg.category.unique())
    grid = pd.MultiIndex.from_product(
        [sorted(agg.store_key.unique()), cats, sorted(agg.date.unique())],
        names=["store_key", "category", "date"],
    )
    df = (
        agg.set_index(["store_key", "category", "date"])[["net_sales"]]
        .reindex(grid, fill_value=0.0)
        .reset_index()
    )
    df = df.sort_values(["store_key", "category", "date"])
    g = df.groupby(["store_key", "category"]).net_sales
    for lag in (7, 14, 21):
        df[f"lag{lag}"] = g.shift(lag)
    df["mean7_lag7"] = g.transform(lambda s: s.shift(HORIZON_DAYS).rolling(7).mean())
    df["dow"] = df.date.dt.weekday
    df["cat_code"] = df.category.map({c: i for i, c in enumerate(cats)})
    df["square_meters"] = df.store_key.map(
        dict(zip(dim_store.store_key, dim_store.square_meters, strict=True))
    )
    return df.dropna(subset=["lag21", "mean7_lag7"]).reset_index(drop=True)


def train_and_backtest(agg: pd.DataFrame, dim_store: pd.DataFrame) -> ForecastResult:
    df = features(agg, dim_store)
    cut = df.date.max() - pd.Timedelta(days=HOLDOUT_DAYS - 1)
    train, test = df[df.date < cut], df[df.date >= cut]
    model = GradientBoostingRegressor(**MODEL_PARAMS).fit(train[FEATURES], train.net_sales)
    pred = np.clip(model.predict(test[FEATURES]), 0, None)
    out = test[["store_key", "category", "date", "net_sales", "lag7"]].assign(forecast=pred.round(2))
    return ForecastResult(
        wape_model=round(wape(test.net_sales.to_numpy(), pred), 4),
        wape_naive=round(wape(test.net_sales.to_numpy(), test.lag7.to_numpy()), 4),
        rows_train=len(train),
        rows_test=len(test),
        model=model,
        predictions=out.reset_index(drop=True),
    )
