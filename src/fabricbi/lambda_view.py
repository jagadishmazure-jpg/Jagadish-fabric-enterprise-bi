"""Lambda serving view: batch history from gold plus today's numbers from the hot path.

The cold path is complete and corrected but runs once a day. The hot path is immediate but only
covers the hours since the last batch. The serving view stitches them at the batch cut-off:

    date <  cutoff   -> gold.agg_daily_sales (source = "batch")
    date >= cutoff   -> hot-path windows rolled up per store and day (source = "speed", partial)

Speed rows from before the cut-off are dropped, so a day is never counted twice. When the next
batch lands, the cut-off moves forward and the batch numbers replace the speed numbers."""

from __future__ import annotations

from datetime import datetime

import pandas as pd


def serving_view(
    gold_daily: pd.DataFrame, dim_store: pd.DataFrame, hot_sales_windows: list[dict], cutoff: datetime
) -> pd.DataFrame:
    sid = dict(zip(dim_store.store_key, dim_store.store_id, strict=True))
    batch = (
        gold_daily.assign(
            store_id=gold_daily.store_key.map(sid),
            date=pd.to_datetime(gold_daily.date_key.astype(str), format="%Y%m%d"),
        )
        .groupby(["store_id", "date"], as_index=False)
        .agg(net_sales=("net_sales", "sum"), transactions=("transactions", "sum"))
    )
    batch = batch[batch.date < pd.Timestamp(cutoff)].assign(source="batch", is_partial=False)

    hot = pd.DataFrame(hot_sales_windows)
    if hot.empty:
        speed = batch.head(0)
    else:
        hot = hot[hot.window_start >= pd.Timestamp(cutoff)]
        speed = (
            hot.assign(date=hot.window_start.dt.normalize())
            .groupby(["store_id", "date"], as_index=False)
            .agg(net_sales=("revenue", "sum"), transactions=("transactions", "sum"))
            .assign(source="speed", is_partial=True)
        )
    out = pd.concat([batch, speed], ignore_index=True)
    out["net_sales"] = out.net_sales.round(2)
    out["transactions"] = out.transactions.astype("int64")
    return out.sort_values(["store_id", "date"]).reset_index(drop=True)


def today_vs_typical(view: pd.DataFrame, store_id: str) -> dict:
    """Today's partial sales for a store next to its average for the same weekday in batch history."""
    s = view[view.store_id == store_id]
    today = s[s.source == "speed"]
    if today.empty:
        return {
            "store_id": store_id,
            "today_so_far": None,
            "typical_full_day": None,
            "batch_days": int((s.source == "batch").sum()),
        }
    day = today.date.iloc[-1]
    same_dow = s[(s.source == "batch") & (s.date.dt.weekday == day.weekday())]
    return {
        "store_id": store_id,
        "today_so_far": float(today.net_sales.iloc[-1]),
        "typical_full_day": round(float(same_dow.net_sales.mean()), 2) if len(same_dow) else None,
        "batch_days": int((s.source == "batch").sum()),
    }
