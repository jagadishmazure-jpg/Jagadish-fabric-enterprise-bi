"""Event-time tumbling windows with a watermark, and anomaly detection on closed windows.

This is the Python twin of the KQL in `kql/` (Eventhouse) and the Eventstream processing it
stands for. The constants below are parsed from the KQL files by a test, so the two cannot
drift apart silently.

* Windows are 5 minutes, keyed by event time, not arrival time.
* The watermark trails the newest event time seen by `ALLOWED_LATENESS`. A window closes when the
  watermark passes its end; an event whose window is already closed goes to `late_events`
  (the dead-letter output) instead of silently changing a published number.
* On each closed window the detectors run:
    freezer_warm    a freezer's average is above WARM_THRESHOLD_C for WARM_WINDOWS windows in a row
    sensor_offline  a device has sent nothing for longer than OFFLINE_AFTER
    sales_spike     a store's window revenue is SPIKE_Z standard deviations above its trailing
                    BASELINE_WINDOWS windows
  Each incident raises one alert and stays quiet until it clears."""

from __future__ import annotations

import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fabricbi.hotpath.stream import Event

WINDOW_SIZE = timedelta(minutes=5)
ALLOWED_LATENESS = timedelta(minutes=5)
WARM_THRESHOLD_C = -12.0
WARM_WINDOWS = 3
OFFLINE_AFTER = timedelta(minutes=15)
SPIKE_Z = 3.0
BASELINE_WINDOWS = 12
MIN_SPIKE_REVENUE = 300.0


def window_start(t: datetime) -> datetime:
    size = int(WINDOW_SIZE.total_seconds() // 60)
    return t.replace(minute=t.minute - t.minute % size, second=0, microsecond=0)


@dataclass
class Alert:
    kind: str
    key: str
    window_start: datetime
    detail: str
    severity: str = "warning"


@dataclass
class HotPathResult:
    sales_windows: list[dict] = field(default_factory=list)
    sensor_windows: list[dict] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    late_events: list[Event] = field(default_factory=list)
    accepted: int = 0


class HotPathProcessor:
    def __init__(self) -> None:
        self.watermark: datetime | None = None
        self.open: dict[datetime, dict] = {}
        self.closed_until: datetime | None = None
        self.result = HotPathResult()
        self.stores: set[str] = set()
        self.devices: set[str] = set()
        self.last_seen: dict[str, datetime] = {}
        self.warm_run: dict[str, int] = defaultdict(int)
        self.active: set[tuple[str, str]] = set()
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=BASELINE_WINDOWS))

    def _bucket(self, ws: datetime) -> dict:
        return self.open.setdefault(ws, {"pos": defaultdict(lambda: [0.0, 0]), "sensor": defaultdict(list)})

    def process(self, e: Event) -> None:
        ws = window_start(e.event_time)
        if self.closed_until is not None and ws < self.closed_until:
            self.result.late_events.append(e)
            return
        self.result.accepted += 1
        b = self._bucket(ws)
        if e.kind == "pos":
            self.stores.add(e.key)
            acc = b["pos"][e.key]
            acc[0] += e.payload["basket_value"]
            acc[1] += 1
        else:
            self.devices.add(e.key)
            b["sensor"][e.key].append(e.payload["temp_c"])
            self.last_seen[e.key] = max(self.last_seen.get(e.key, e.event_time), e.event_time)
        wm = e.event_time - ALLOWED_LATENESS
        if self.watermark is None or wm > self.watermark:
            self.watermark = wm
            self._close(until=self.watermark)

    def _close(self, until: datetime) -> None:
        for ws in sorted(w for w in self.open if w + WINDOW_SIZE <= until):
            self._emit(ws, self.open.pop(ws))
            self.closed_until = ws + WINDOW_SIZE

    def flush(self) -> HotPathResult:
        for ws in sorted(self.open):
            self._emit(ws, self.open.pop(ws))
            self.closed_until = ws + WINDOW_SIZE
        return self.result

    def _raise(self, kind: str, key: str, ws: datetime, detail: str, severity: str = "warning") -> None:
        if (kind, key) not in self.active:
            self.active.add((kind, key))
            self.result.alerts.append(Alert(kind, key, ws, detail, severity))

    def _clear(self, kind: str, key: str) -> None:
        self.active.discard((kind, key))

    def _emit(self, ws: datetime, b: dict) -> None:
        we = ws + WINDOW_SIZE
        for s in sorted(self.stores):
            revenue, txns = b["pos"].get(s, [0.0, 0])
            self.result.sales_windows.append(
                {"store_id": s, "window_start": ws, "revenue": round(revenue, 2), "transactions": txns}
            )
            hist = self.history[s]
            if len(hist) == BASELINE_WINDOWS:
                mu = statistics.fmean(hist)
                sd = statistics.pstdev(hist) or 1.0
                z = (revenue - mu) / sd
                if z >= SPIKE_Z and revenue >= MIN_SPIKE_REVENUE:
                    self._raise(
                        "sales_spike",
                        s,
                        ws,
                        f"revenue {revenue:.0f} vs baseline {mu:.0f} (z={z:.1f})",
                        "info",
                    )
                elif z < SPIKE_Z / 2:
                    self._clear("sales_spike", s)
            hist.append(revenue)
        for d in sorted(self.devices):
            temps = b["sensor"].get(d, [])
            if temps:
                avg = statistics.fmean(temps)
                self.result.sensor_windows.append(
                    {
                        "device_id": d,
                        "window_start": ws,
                        "avg_temp_c": round(avg, 2),
                        "max_temp_c": max(temps),
                        "readings": len(temps),
                    }
                )
                self.warm_run[d] = self.warm_run[d] + 1 if avg > WARM_THRESHOLD_C else 0
                if self.warm_run[d] >= WARM_WINDOWS:
                    self._raise(
                        "freezer_warm",
                        d,
                        ws,
                        f"avg {avg:.1f} C above {WARM_THRESHOLD_C} C for {self.warm_run[d]} windows",
                        "critical",
                    )
                elif self.warm_run[d] == 0:
                    self._clear("freezer_warm", d)
                self._clear("sensor_offline", d)
            elif we - self.last_seen.get(d, we) > OFFLINE_AFTER:
                self._raise("sensor_offline", d, ws, f"no readings since {self.last_seen[d]:%H:%M}")


def run(events: list[Event]) -> HotPathResult:
    p = HotPathProcessor()
    for e in events:
        p.process(e)
    return p.flush()
