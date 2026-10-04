"""Gold: a star schema for BI and the data agent, plus a daily aggregate for forecasting.

    dim_date      one row per calendar day (date_key = yyyymmdd)
    dim_store     store, city, region (region drives row-level security)
    dim_product   SKU, category, brand, list price, unit cost (unit cost is finance-only)
    dim_customer  loyalty members from the mirrored database (email/phone are PII), plus key -1
                  for guest checkouts
    fact_sales    one row per POS line: quantity, net amount, cost amount
    fact_freezer_daily  daily temperature summary per freezer
    agg_daily_sales     net sales, units and transactions per day, store and category

Surrogate keys are dense integers assigned in a stable order, so a rebuild from the same silver
data gives identical keys. Every table is checked against its schema contract before it is
written."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from fabricbi.coldpath import contracts
from fabricbi.coldpath.silver import ContractError
from fabricbi.context import RunContext

WARM_THRESHOLD_C = -12.0


def _keyed(df: pd.DataFrame, natural: str, key: str) -> pd.DataFrame:
    df = df.sort_values(natural).reset_index(drop=True)
    df.insert(0, key, range(1, len(df) + 1))
    return df


def write_contracted(ctx: RunContext, name: str, df: pd.DataFrame, inputs: list[str], process: str) -> None:
    v = contracts.validate(df, contracts.load(f"gold.{name}"))
    if v:
        raise ContractError(f"gold.{name}: " + "; ".join(f"{x.column}:{x.rule}" for x in v[:5]))
    ctx.write("gold", name, df, inputs, process)


def build_gold(ctx: RunContext, through_day: pd.Timestamp | None = None) -> dict[str, int]:
    lake = ctx.lake
    with ctx.telemetry.span("gold.build", **{"fabricbi.layer": "gold"}):
        pos = lake.read("silver", "pos_lines")
        stores = lake.read("silver", "stores")
        products = lake.read("silver", "products")
        customers = lake.read("silver", "customers")
        fz = lake.read("silver", "freezer_readings")

        first = pos.ts.min().normalize()
        last = (through_day or pos.ts.max().normalize() + timedelta(days=1)).normalize()
        days = pd.date_range(first, last, freq="D")
        dim_date = pd.DataFrame(
            {
                "date_key": days.strftime("%Y%m%d").astype("int64"),
                "date": days,
                "day_of_week": days.day_name(),
                "iso_week": days.isocalendar().week.astype("int64").to_numpy(),
                "month": days.month.astype("int64"),
                "is_weekend": days.weekday >= 5,
            }
        )
        write_contracted(ctx, "dim_date", dim_date, ["silver.pos_lines"], "nb_gold_dim_date")

        dim_store = _keyed(
            stores[["store_id", "store_name", "city", "region", "square_meters"]].copy(),
            "store_id",
            "store_key",
        )
        dim_store["square_meters"] = dim_store.square_meters.astype("int64")
        write_contracted(ctx, "dim_store", dim_store, ["silver.stores"], "nb_gold_dim_store")

        dim_product = _keyed(
            products[
                [
                    "sku",
                    "product_name",
                    "category",
                    "brand",
                    "list_price",
                    "unit_cost",
                    "is_organic",
                    "is_frozen",
                ]
            ].copy(),
            "sku",
            "product_key",
        )
        write_contracted(ctx, "dim_product", dim_product, ["silver.products"], "nb_gold_dim_product")

        region_of = dict(zip(stores.store_id, stores.region, strict=True))
        cust = customers.assign(home_region=customers.home_store_id.map(region_of))[
            ["customer_id", "first_name", "email", "phone", "tier", "home_region"]
        ]
        dim_customer = _keyed(cust.copy(), "customer_id", "customer_key")
        guest = pd.DataFrame(
            [
                {
                    "customer_key": -1,
                    "customer_id": "GUEST",
                    "first_name": "Guest",
                    "email": "",
                    "phone": "",
                    "tier": "none",
                    "home_region": "n/a",
                }
            ]
        )
        dim_customer = pd.concat([guest, dim_customer], ignore_index=True)
        write_contracted(
            ctx, "dim_customer", dim_customer, ["silver.customers", "silver.stores"], "nb_gold_dim_customer"
        )

        sk = dict(zip(dim_store.store_id, dim_store.store_key, strict=True))
        pk = dict(zip(dim_product.sku, dim_product.product_key, strict=True))
        ck = dict(zip(dim_customer.customer_id, dim_customer.customer_key, strict=True))
        cost = dict(zip(dim_product.sku, dim_product.unit_cost, strict=True))
        net = (pos.qty * pos.unit_price * (1 - pos.discount_pct)).round(2)
        fact = pd.DataFrame(
            {
                "sales_line_id": (pos.txn_id + "-" + pos.line_no.astype(str)),
                "txn_id": pos.txn_id,
                "date_key": pos.ts.dt.strftime("%Y%m%d").astype("int64"),
                "store_key": pos.store_id.map(sk).astype("int64"),
                "product_key": pos.sku.map(pk).astype("int64"),
                # a member deleted from the source after buying is kept as a guest sale
                "customer_key": pos.customer_id.map(ck).fillna(-1).astype("int64"),
                "qty": pos.qty.astype("int64"),
                "net_amount": net,
                "cost_amount": (pos.qty * pos.sku.map(cost)).round(2),
            }
        )
        write_contracted(
            ctx,
            "fact_sales",
            fact,
            ["silver.pos_lines", "gold.dim_store", "gold.dim_product", "gold.dim_customer", "gold.dim_date"],
            "nb_gold_fact_sales",
        )

        fz = fz.assign(
            date_key=fz.ts.dt.strftime("%Y%m%d").astype("int64"), warm=fz.temp_c > WARM_THRESHOLD_C
        )
        ffd = (
            fz.groupby(["date_key", "store_id", "device_id"], as_index=False)
            .agg(
                avg_temp_c=("temp_c", "mean"),
                max_temp_c=("temp_c", "max"),
                hours_above_threshold=("warm", "sum"),
            )
            .assign(
                store_key=lambda d: d.store_id.map(sk).astype("int64"),
                avg_temp_c=lambda d: d.avg_temp_c.round(2),
            )
        )[["date_key", "store_key", "device_id", "avg_temp_c", "max_temp_c", "hours_above_threshold"]]
        ffd["hours_above_threshold"] = ffd.hours_above_threshold.astype("int64")
        write_contracted(
            ctx,
            "fact_freezer_daily",
            ffd,
            ["silver.freezer_readings", "gold.dim_store"],
            "nb_gold_fact_freezer",
        )

        cat = dict(zip(dim_product.product_key, dim_product.category, strict=True))
        agg = (
            fact.assign(category=fact.product_key.map(cat))
            .groupby(["date_key", "store_key", "category"], as_index=False)
            .agg(net_sales=("net_amount", "sum"), units=("qty", "sum"), transactions=("txn_id", "nunique"))
        )
        agg["net_sales"] = agg.net_sales.round(2)
        agg["units"] = agg.units.astype("int64")
        agg["transactions"] = agg.transactions.astype("int64")
        write_contracted(
            ctx, "agg_daily_sales", agg, ["gold.fact_sales", "gold.dim_product"], "nb_gold_agg_daily"
        )
    return {
        t: ctx.lake.metadata()[f"gold.{t}"]["rows"]
        for t in (
            "dim_date",
            "dim_store",
            "dim_product",
            "dim_customer",
            "fact_sales",
            "fact_freezer_daily",
            "agg_daily_sales",
        )
    }
