import copy
import re
from datetime import datetime, timedelta

import pytest

from fabricbi.coldpath.contracts import all_contracts
from fabricbi.finops import capacity
from fabricbi.governance import labels
from fabricbi.governance.catalog import Catalog
from fabricbi.governance.lineage import LineageGraph
from fabricbi.governance.products import bump_for, consumers_by_asset, load_products, validate_product
from fabricbi.observability.slo import error_budget, freshness
from fabricbi.paths import ROOT
from fabricbi.serve.vector_store import VectorStore


@pytest.fixture(scope="module")
def catalog(run):
    return Catalog.build(run.ctx.lineage, run.lake.metadata())


def test_catalog_has_no_findings(catalog):
    assert catalog.check() == []


def test_catalog_flags_unowned_and_downgraded_assets(catalog):
    c = copy.deepcopy(catalog)
    c.entries["gold.fact_sales"]["owner"] = ""
    c.entries["gold.agg_daily_sales"].pop("declassify")
    found = c.check()
    assert any("gold.fact_sales has no owner" in f for f in found)
    assert any(f.startswith("gold.agg_daily_sales is General but reads Confidential") for f in found)


def test_lineage_traces_sources_to_serving(run):
    g = run.ctx.lineage
    up = g.upstream("gold.serving_sales_daily")
    assert {"source.pos_export", "source.event_hubs.pos"} <= up
    assert not g.has_cycle()
    assert "flowchart" in g.to_mermaid()


def test_lineage_round_trips_and_exports_openlineage(run, tmp_path):
    g = run.ctx.lineage
    g.save(tmp_path / "l.json")
    again = LineageGraph.load(tmp_path / "l.json")
    assert again.assets == g.assets
    events = g.to_openlineage()
    assert events and all("inputs" in e and "outputs" in e for e in events)


def test_impact_of_a_source_change_names_consumers(run):
    impact = run.ctx.lineage.impact("source.pos_export", consumers_by_asset(load_products()))
    assert impact
    assert any("powerbi.retail-sales-report" in v for v in impact.values())


def test_label_order_and_clearance():
    assert labels.strictest(["General", "Highly Confidential", "Confidential"]) == "Highly Confidential"
    assert labels.at_most("Confidential", "Highly Confidential")
    assert not labels.at_most("Highly Confidential", "General")
    assert labels.clearance_for(["analyst", "pii_reader"]) == "Highly Confidential"


def test_describe_shows_classified_columns(catalog):
    d = catalog.describe("gold.dim_customer")
    assert d["label"] == "Highly Confidential"
    assert {"email", "phone"} <= set(d["classified_columns"])


def test_all_data_products_are_valid():
    names = {n for n in all_contracts()}
    prods = load_products()
    assert len(prods) == 5
    for p in prods.values():
        assert validate_product(p, names) == [], p["name"]


def test_product_validation_catches_problems():
    p = copy.deepcopy(load_products()["retail-sales"])
    p["version"] = "v2"
    p["consumers"] = []
    p["schema_contracts"].append("gold.nope")
    errs = validate_product(p, set(all_contracts()))
    assert len(errs) >= 3


def test_restricted_products_are_not_shared_externally():
    for p in load_products().values():
        if labels.rank(p["sensitivity"]) > labels.rank("General"):
            assert not p["sharing"].get("external_share"), p["name"]


@pytest.mark.parametrize("change,expected", [("breaking", "2.0.0"), ("additive", "1.3.0"), ("none", "1.2.1")])
def test_version_bump(change, expected):
    assert bump_for(change, "1.2.0") == expected


def test_vector_store_filters_by_label():
    vs = VectorStore.build()
    general = [c.label for c, _ in vs.search("loyalty members contact details", k=10, clearance="General")]
    assert all(labels.at_most(lbl, "General") for lbl in general)
    top = [
        c.source
        for c, _ in vs.search("loyalty members contact details", k=3, clearance="Highly Confidential")
    ]
    assert "contracts/products/loyalty-members.yaml" in top


def test_retrieval_finds_measure_definition():
    top = [c.source for c, _ in VectorStore.build().search("how is average basket calculated", k=3)]
    assert "semantic-model/retail_sales.yaml" in top


def test_freshness_statuses():
    p = {"name": "x", "slo": {"freshness_hours": 10}}
    now = datetime(2000, 1, 1, 12)
    assert freshness(p, now - timedelta(hours=7), now).status == "ok"
    assert freshness(p, now - timedelta(hours=9), now).status == "warning"
    assert freshness(p, now - timedelta(hours=11), now).status == "breach"
    assert freshness(p, None, now).status == "breach"


def test_error_budget():
    assert error_budget(["ok"] * 99 + ["breach"])["met"]
    assert not error_budget(["ok"] * 98 + ["breach"] * 2)["met"]


def test_pipeline_emits_telemetry(run):
    t = run.ctx.telemetry
    names = {s.name for s in t.spans}
    assert {"mirroring.sync", "enrich.tickets", "enrich.forecast", "hotpath.eventstream"} <= names
    assert t.counter("fabricbi.hotpath.late_events") == 48


def test_capacity_sizing_picks_f4_with_headroom():
    s = capacity.size()
    assert s.sku == 4
    assert s.utilisation <= 0.8
    assert s.monthly_reserved_usd < s.monthly_payg_usd


def test_capacity_grows_with_load():
    assert capacity.size(scale=25).sku > capacity.size(scale=5).sku > capacity.size().sku


def test_prod_iac_sku_matches_estimate():
    s = capacity.size()
    tf = (ROOT / "infra/terraform/envs/prod.tfvars").read_text()
    bicep = (ROOT / "infra/main.parameters.prod.json").read_text()
    assert re.search(rf'fabric_sku\s*=\s*"F{s.sku}"', tf)
    assert f'"F{s.sku}"' in bicep


def test_cost_report_is_labelled_as_estimate():
    text = capacity.markdown(capacity.size())
    assert "estimate" in text.lower()
