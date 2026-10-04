import re
from datetime import datetime, timedelta

import pytest

from fabricbi.hotpath import stream, windows
from fabricbi.paths import KQL_DIR

DAY = datetime(2000, 1, 3)  # arbitrary calendar day for the simulator


def test_three_planted_incidents_are_alerted(run):
    assert {(a.kind, a.key) for a in run.hot.alerts} == {
        ("sales_spike", stream.SPIKE_STORE),
        ("freezer_warm", stream.WARM_DEVICE),
        ("sensor_offline", stream.OFFLINE_DEVICE),
    }


def test_late_events_are_counted_not_merged(run):
    assert len(run.hot.late_events) == 48
    assert run.hot.accepted > 0


def test_stream_is_delivered_in_ingest_order():
    ev = stream.simulate(DAY)
    assert [e.ingest_time for e in ev] == sorted(e.ingest_time for e in ev)
    assert any(e.ingest_time - e.event_time > windows.ALLOWED_LATENESS for e in ev)


def test_window_start_aligns_to_five_minutes():
    assert windows.window_start(datetime(2000, 1, 1, 10, 7, 59)) == datetime(2000, 1, 1, 10, 5)


def test_sales_windows_are_complete_per_store(run):
    w = run.hot.sales_windows
    assert {x["store_id"] for x in w} == set(stream.STORES)
    assert all(x["window_start"].minute % 5 == 0 for x in w)


def test_single_warm_window_does_not_alert():
    t0 = DAY.replace(hour=9)
    ev = []
    for i in range(12):
        t = t0 + timedelta(minutes=5 * i)
        temp = -5.0 if i == 4 else -18.0
        ev.append(
            stream.Event(
                "sensor", "S001-FZ1", t, t, {"temp_c": temp, "device_id": "S001-FZ1", "store_id": "S001"}
            )
        )
    res = windows.run(ev)
    assert not [a for a in res.alerts if a.kind == "freezer_warm"]


def test_quiet_stream_has_no_spike():
    ev = [e for e in stream.simulate(DAY) if e.key != stream.SPIKE_STORE and e.kind == "pos"]
    assert not [a for a in windows.run(ev).alerts if a.kind == "sales_spike"]


def _lets(path):
    out = {}
    for name, val in re.findall(r"^let (\w+) = ([^;]+);", path.read_text(), re.M):
        v = val.strip()
        if m := re.fullmatch(r"(\d+)m", v):
            out[name] = timedelta(minutes=int(m.group(1)))
        elif m := re.fullmatch(r"(\d+)h", v):
            out[name] = timedelta(hours=int(m.group(1)))
        else:
            out[name] = float(v)
    return out


@pytest.mark.parametrize(
    "file,name,expected",
    [
        ("sales_5min.kql", "window_size", windows.WINDOW_SIZE),
        ("freezer_alerts.kql", "warm_threshold_c", windows.WARM_THRESHOLD_C),
        ("freezer_alerts.kql", "warm_windows", windows.WARM_WINDOWS),
        ("late_events.kql", "allowed_lateness", windows.ALLOWED_LATENESS),
        ("sales_spike.kql", "spike_z", windows.SPIKE_Z),
        ("sales_spike.kql", "baseline_windows", windows.BASELINE_WINDOWS),
        ("sales_spike.kql", "min_spike_revenue", windows.MIN_SPIKE_REVENUE),
        ("sensor_offline.kql", "offline_after", windows.OFFLINE_AFTER),
    ],
)
def test_kql_constants_match_python(file, name, expected):
    assert _lets(KQL_DIR / file)[name] == expected


def test_every_kql_file_reads_a_declared_table():
    tables = set(re.findall(r"\.create(?:-merge)? table (\w+)", (KQL_DIR / "tables.kql").read_text()))
    assert tables
    for f in KQL_DIR.glob("*.kql"):
        if f.name == "tables.kql":
            continue
        assert any(re.search(rf"\b{t}\b", f.read_text()) for t in tables), f.name
