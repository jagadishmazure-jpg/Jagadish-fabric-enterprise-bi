import copy

import pandas as pd
import pytest

from fabricbi.coldpath import contracts, quality
from fabricbi.coldpath.silver import redact


def test_every_contract_loads_with_primary_key():
    allc = contracts.all_contracts()
    assert len(allc) >= 12
    for name, c in allc.items():
        assert c.get("primary_key"), name
        assert {k for col in c["columns"] for k in col} >= {"name", "type"}, name


@pytest.mark.parametrize(
    "table",
    ["fact_sales", "dim_store", "dim_product", "dim_customer", "dim_date", "agg_daily_sales", "fact_ticket"],
)
def test_gold_tables_satisfy_their_contracts(lake, table):
    assert contracts.validate(lake.read("gold", table), contracts.load(f"gold.{table}")) == []


def test_validate_catches_null_and_duplicate_key():
    c = contracts.load("gold.dim_store")
    df = pd.DataFrame(
        {
            "store_key": [1, 1],
            "store_id": ["S001", None],
            "store_name": ["a", "b"],
            "city": ["x", "y"],
            "region": ["North", "Mars"],
            "square_meters": [1000, 50],
        }
    )
    found = {(v.column, v.rule) for v in contracts.validate(df, c)}
    cols = {col for col, _ in found}
    assert {"store_key", "store_id", "region", "square_meters"} <= cols


def test_adding_nullable_column_is_minor():
    old = contracts.load("gold.dim_store")
    new = copy.deepcopy(old)
    new["columns"].append({"name": "opened_year", "type": "int", "nullable": True})
    assert contracts.compatibility(old, new)[0] == "additive"
    new["columns"][-1]["nullable"] = False
    assert contracts.compatibility(old, new)[0] == "breaking"


def test_type_change_and_key_change_are_breaking():
    old = contracts.load("gold.dim_store")
    new = copy.deepcopy(old)
    new["columns"][5]["type"] = "string"
    assert contracts.compatibility(old, new)[0] == "breaking"
    new = copy.deepcopy(old)
    new["primary_key"] = ["store_id"]
    assert contracts.compatibility(old, new)[0] == "breaking"
    assert contracts.compatibility(old, copy.deepcopy(old)) == ("none", [])


def test_dropping_column_is_breaking():
    old = contracts.load("gold.dim_store")
    new = copy.deepcopy(old)
    new["columns"] = [c for c in new["columns"] if c["name"] != "city"]
    level, reasons = contracts.compatibility(old, new)
    assert level == "breaking" and reasons == ["column city removed"]


def test_quality_rules_quarantine_with_reason():
    df = pd.DataFrame({"qty": [1, -2, 3], "sku": ["A", "A", "Z"]})
    good, bad, rep = quality.apply_rules(
        df, [quality.in_range("qty", lo=0), quality.references("sku", {"A"}, "sku->products")], "t"
    )
    assert len(good) == 1 and len(bad) == 2
    assert rep.quarantined == 2
    assert not rep.passed(max_quarantine_rate=0.5)


def test_silver_quarantine_and_dedupe_counts(run):
    rep = run.ctx.dq_reports["pos_lines"]
    assert rep.quarantined == 2
    assert rep.by_rule["dedupe:exact_duplicate"] == 3
    assert rep.passed()


def test_quarantine_table_keeps_rule_names(lake):
    q = lake.read("silver", "pos_lines_quarantine")
    assert len(q) == 2
    rule_col = next(c for c in q.columns if "rule" in c)
    assert set(q[rule_col]) == {"range:qty", "fk:sku->products"}


def test_catalog_defects_are_flagged_not_dropped(run, lake):
    rep = run.ctx.dq_reports["products"]
    assert rep.by_rule == {"warn:price_as_text": 1, "warn:category_unassigned": 1}
    assert len(lake.read("silver", "products")) == 40


def test_redact_removes_email_and_phone():
    out = redact("Mail me at pat.lee@example.com or call 555-123-4567")
    assert "@" not in out and "4567" not in out


def test_silver_tickets_have_no_pii(lake):
    t = lake.read("silver", "support_tickets")
    assert not t.text_redacted.str.contains("@").any()
    assert "text" not in t.columns
