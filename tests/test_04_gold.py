import pandas as pd

from fabricbi.coldpath.gold import WARM_THRESHOLD_C as GOLD_WARM
from fabricbi.hotpath.windows import WARM_THRESHOLD_C as HOT_WARM


def test_fact_sales_foreign_keys_resolve(lake):
    f = lake.read("gold", "fact_sales")
    for dim, key in [
        ("dim_store", "store_key"),
        ("dim_product", "product_key"),
        ("dim_customer", "customer_key"),
        ("dim_date", "date_key"),
    ]:
        assert f[key].isin(lake.read("gold", dim)[key]).all(), dim


def test_fact_sales_matches_clean_silver(lake):
    assert len(lake.read("gold", "fact_sales")) == len(lake.read("silver", "pos_lines"))


def test_unknown_customer_member_exists(lake):
    c = lake.read("gold", "dim_customer")
    assert (c.customer_key == -1).sum() == 1


def test_deleted_customer_not_in_dimension(lake):
    assert "C00300" not in set(lake.read("gold", "dim_customer").customer_id)


def test_daily_aggregate_reconciles_with_fact(lake):
    f = lake.read("gold", "fact_sales")
    a = lake.read("gold", "agg_daily_sales")
    assert round(f.net_amount.sum(), 2) == round(a.net_sales.sum(), 2)


def test_dim_date_is_contiguous(lake):
    d = pd.to_datetime(lake.read("gold", "dim_date").date_key.astype(str), format="%Y%m%d").sort_values()
    assert (d.diff().dropna() == pd.Timedelta(days=1)).all()


def test_freezer_daily_flags_the_warm_afternoon(lake):
    fz = lake.read("gold", "fact_freezer_daily")
    hot = fz[fz.hours_above_threshold > 0]
    assert set(hot.device_id) == {"S004-FZ1"}
    assert (hot.max_temp_c > GOLD_WARM).all()


def test_warm_threshold_is_shared():
    assert GOLD_WARM == HOT_WARM


def test_gold_writes_record_lineage(run):
    up = run.ctx.lineage.upstream("gold.fact_sales")
    assert "silver.pos_lines" in up and "source.pos_export" in up
