import pandas as pd

from fabricbi.coldpath.bronze import BronzeIngest
from fabricbi.coldpath.mirroring import MirrorReplica, OperationalDb
from fabricbi.context import RunContext
from fabricbi.domain.synth import generate


def test_bronze_keeps_source_rows_and_metadata(lake, run):
    b = lake.read("bronze", "pos_lines")
    assert len(b) == len(pd.read_csv(run.sources.pos_csv))
    meta = [c for c in b.columns if c.startswith("_")]
    assert len(meta) == 3


def test_bronze_is_idempotent(tmp_path):
    src = generate(tmp_path / "src", days=7)
    ctx = RunContext(tmp_path / "lake")
    first = BronzeIngest(ctx).run(src)
    rows = len(ctx.lake.read("bronze", "pos_lines"))
    second = BronzeIngest(ctx).run(src)
    assert "skipped" not in first
    assert second == {"skipped": 4}
    assert len(ctx.lake.read("bronze", "pos_lines")) == rows


def _db(tmp_path):
    src = generate(tmp_path / "src", days=7)
    return OperationalDb(src.opdb)


def test_mirror_applies_cdc_including_deletes(tmp_path):
    db = _db(tmp_path)
    m = MirrorReplica(tmp_path / "lake")
    m.sync(db)
    assert m.lag(db) == 0
    cust = m.read("customers")
    assert "C00300" not in set(cust.customer_id)
    assert len(m.read("stores")) == 12
    assert set(m.read("stores").store_id) == set(db.table("stores").store_id)


def test_mirror_replay_is_idempotent(tmp_path):
    db = _db(tmp_path)
    m = MirrorReplica(tmp_path / "lake")
    m.sync(db)
    before = m.read("customers")
    stats = m.sync(db)
    assert stats.applied == 0
    pd.testing.assert_frame_equal(before, m.read("customers"))


def test_mirror_lag_and_partial_sync(tmp_path):
    db = _db(tmp_path)
    m = MirrorReplica(tmp_path / "lake")
    m.sync(db, max_changes=1)
    assert m.lag(db) > 0
    db.update("stores", "S001", {"store_name": "Fernhill Alder Falls Market"})
    m.sync(db)
    assert m.lag(db) == 0
    assert "Fernhill Alder Falls Market" in set(m.read("stores").store_name)


def test_checkpoint_survives_restart(tmp_path):
    db = _db(tmp_path)
    MirrorReplica(tmp_path / "lake").sync(db)
    again = MirrorReplica(tmp_path / "lake")
    assert again.checkpoint == db.max_lsn()


def test_pipeline_mirror_has_no_lag(run):
    assert run.mirror_lag == 0


def test_mirror_is_exposed_as_shortcut(lake):
    assert {"opdb_customers", "opdb_stores"} <= set(lake.shortcuts())
    assert len(lake.read_shortcut("opdb_stores")) == 12
