"""Ignite patterns: HorizonDB incremental mirror, Fabric app pages, Fabric IQ row-level security."""

import re
from pathlib import Path

import pytest

from fabricbi.coldpath.contracts import load, validate
from fabricbi.ignite.fabric_app import PAGES, RetailReviewApp
from fabricbi.ignite.fabric_iq import TOOL_NAME, FabricIqTool
from fabricbi.ignite.horizondb import CONTRACT, DEMO_ROWS, HorizonContractError, HorizonMirror, HorizonSource
from fabricbi.paths import ROOT


def _source(tmp_path: Path) -> HorizonSource:
    source = HorizonSource(tmp_path / "horizondb.db")
    source.seed_demo()
    return source


def test_initial_sync_matches_source_and_contract(tmp_path):
    source = _source(tmp_path)
    mirror = HorizonMirror(tmp_path / "lake")
    stats = mirror.sync(source)
    replica = mirror.read()
    assert stats.applied == len(DEMO_ROWS)
    assert stats.inserts == len(DEMO_ROWS) and stats.updates == 0 and stats.deletes == 0
    assert mirror.lag(source) == 0
    assert len(replica) == len(source.table())
    assert set(replica.redemption_id) == {row["redemption_id"] for row in DEMO_ROWS}
    assert validate(replica, load(CONTRACT)) == []
    source.close()


def test_replay_applies_nothing(tmp_path):
    source = _source(tmp_path)
    mirror = HorizonMirror(tmp_path / "lake")
    mirror.sync(source)
    before = mirror.read()
    again = mirror.sync(source)
    assert again.applied == 0
    assert mirror.read().to_dict("records") == before.to_dict("records")
    source.close()


def test_incremental_insert_update_delete(tmp_path):
    source = _source(tmp_path)
    mirror = HorizonMirror(tmp_path / "lake")
    mirror.sync(source)
    source.insert(
        {
            "redemption_id": "R-104",
            "store_id": "S001",
            "region": "West",
            "member_id": "C00014",
            "points": 5,
            "redeemed_on": "D03",
        }
    )
    inserted = mirror.sync(source)
    assert inserted.applied == 1 and inserted.inserts == 1
    assert len(mirror.read()) == len(DEMO_ROWS) + 1
    source.update("R-104", {"points": 9})
    updated = mirror.sync(source)
    assert updated.applied == 1 and updated.updates == 1
    points = mirror.read().set_index("redemption_id").loc["R-104", "points"]
    assert int(points) == 9
    assert len(mirror.read()) == len(DEMO_ROWS) + 1
    source.delete("R-100")
    deleted = mirror.sync(source)
    assert deleted.deletes == 1 and mirror.lag(source) == 0
    assert "R-100" not in set(mirror.read().redemption_id)
    assert len(mirror.read()) == len(source.table())
    source.close()


def test_partial_sync_reports_lag_then_catches_up(tmp_path):
    source = _source(tmp_path)
    mirror = HorizonMirror(tmp_path / "lake")
    first = mirror.sync(source, max_changes=1)
    assert first.applied == 1
    assert mirror.lag(source) == len(DEMO_ROWS) - 1
    rest = mirror.sync(source)
    assert rest.applied == len(DEMO_ROWS) - 1
    assert mirror.lag(source) == 0
    assert set(mirror.read().redemption_id) == {row["redemption_id"] for row in DEMO_ROWS}
    source.close()


def test_checkpoint_survives_new_mirror(tmp_path):
    source = _source(tmp_path)
    HorizonMirror(tmp_path / "lake").sync(source)
    again = HorizonMirror(tmp_path / "lake")
    assert again.checkpoint == source.max_lsn()
    assert again.sync(source).applied == 0
    source.close()


def test_replay_before_checkpoint_is_idempotent(tmp_path):
    source = _source(tmp_path)
    mirror = HorizonMirror(tmp_path / "lake")
    mirror.sync(source, save_checkpoint=False)
    assert mirror.checkpoint == 0
    rows = len(mirror.read())
    mirror.sync(source)
    assert mirror.checkpoint == source.max_lsn()
    assert len(mirror.read()) == rows
    source.close()


def test_failed_contract_does_not_advance_checkpoint(tmp_path):
    source = _source(tmp_path)
    mirror = HorizonMirror(tmp_path / "lake")
    mirror.sync(source)
    source.insert(
        {
            "redemption_id": "R-bad",
            "store_id": "S009",
            "region": "Mars",
            "member_id": "C00099",
            "points": 1,
            "redeemed_on": "D04",
        }
    )
    with pytest.raises(HorizonContractError):
        mirror.sync(source)
    assert mirror.lag(source) == 1
    assert "Mars" not in set(mirror.read().region)
    assert "R-bad" not in set(mirror.read().redemption_id)
    source.close()


def test_postgres_schema_matches_contract():
    sql = (ROOT / "src" / "fabricbi" / "ignite" / "schema.sql").read_text()
    body = re.search(r"CREATE TABLE loyalty_redemptions \((.*?)\);", sql, re.S)
    assert body is not None
    columns = [line.strip().split()[0] for line in body.group(1).splitlines() if line.strip()]
    contract = load(CONTRACT)
    assert columns == [col["name"] for col in contract["columns"]]
    assert contract["primary_key"] == ["redemption_id"]


def test_app_pages_compile_semantic_measures(lake, who):
    app = RetailReviewApp(lake)
    assert {page.page_id for page in PAGES} == {"regional_review", "category_mix", "store_sales"}
    page = app.open_page("regional_review", who("exec.viewer"))
    assert app.model.measures["Net Sales"]["sql"] in page.sql
    assert "dim_store.region" in page.sql
    assert page.measures == ("Net Sales",)
    assert {row[0] for row in page.rows} == {"North", "South", "East", "West"}
    mix = app.open_page("category_mix", who("exec.viewer"))
    assert mix.measures == ("Net Sales", "Units")
    assert app.model.measures["Units"]["sql"] in mix.sql
    assert mix.rows


def test_app_row_level_security_hides_other_region(lake, who):
    app = RetailReviewApp(lake)
    west = app.open_page("regional_review", who("west.manager"))
    north = app.open_page("regional_review", who("north.manager"))
    assert [row[0] for row in west.rows] == ["West"]
    assert [row[0] for row in north.rows] == ["North"]
    north_stores = set(lake.read("gold", "dim_store").query("region == 'North'").store_name)
    seen = {row[0] for row in app.open_page("store_sales", who("west.manager")).rows}
    assert seen
    assert seen.isdisjoint(north_stores)


def test_app_refuses_caller_without_a_role(lake, who):
    app = RetailReviewApp(lake)
    with pytest.raises(PermissionError, match="no_role"):
        app.open_page("regional_review", who("nobody"))


def test_iq_tool_regions_are_disjoint(lake, who):
    tool = FabricIqTool(lake)
    assert tool.spec()["name"] == TOOL_NAME
    west = tool.call(who("west.manager").subject, "Net sales by region")
    north = tool.call(who("north.manager").subject, "Net sales by region")
    assert west["status"] == "answered" and north["status"] == "answered"
    assert [row[0] for row in west["rows"]] == ["West"]
    assert [row[0] for row in north["rows"]] == ["North"]
    assert west["caller"] != north["caller"]
    assert west["regions"] == ["West"] and north["regions"] == ["North"]


def test_iq_west_cannot_read_north_rows(lake, who):
    tool = FabricIqTool(lake)
    west = tool.call(who("west.manager").subject, "Net sales by region")
    # Naming the other region does not widen the caller's row filter.
    asked = tool.call(who("west.manager").subject, "Net sales by region in the North")
    assert asked["status"] == "answered"
    assert [row[0] for row in asked["rows"]] == ["West"]
    assert asked["rows"] == west["rows"]
    north_stores = set(lake.read("gold", "dim_store").query("region == 'North'").store_name)
    by_store = tool.call(who("west.manager").subject, "Net sales by store")
    seen = {row[0] for row in by_store["rows"]}
    assert seen
    assert seen.isdisjoint(north_stores)
    assert "North" not in seen


def test_iq_unknown_caller_is_refused(lake):
    tool = FabricIqTool(lake)
    refused = tool.call("stranger@elsewhere.example", "Net sales by region")
    assert refused["status"] == "refused"
    assert refused["reason"] == "no_role"
    assert refused["rows"] == []
    assert refused["regions"] == []
