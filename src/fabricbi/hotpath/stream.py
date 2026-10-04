"""Simulated event stream for one trading day after the batch cut-off.

Two event types arrive interleaved, the way Event Hubs (POS) and IoT Hub (freezer sensors) would
deliver them to a Fabric Eventstream:

  pos      one checkout: store, transaction id, basket value, item count
  sensor   one freezer reading per device per minute

Each event has an `event_time` (when it happened) and an `ingest_time` (when it reached the
stream). Most arrive within seconds, a few are delayed by minutes, and a handful arrive far too
late, which is what the watermark and late-event handling are for. Three incidents are planted:

  * S007-FZ2 warms up from 11:00 (door left open)
  * S010-FZ1 goes silent between 12:00 and 12:40 (sensor offline)
  * S002 sees a burst of checkouts between 10:00 and 10:30 (sales spike)"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

STORES = [f"S{n:03d}" for n in range(1, 13)]
DEVICES = [f"{s}-FZ{k}" for s in STORES for k in (1, 2)]
WARM_DEVICE, OFFLINE_DEVICE, SPIKE_STORE = "S007-FZ2", "S010-FZ1", "S002"


@dataclass(frozen=True)
class Event:
    kind: str  # pos | sensor
    key: str  # store_id for pos, device_id for sensor
    event_time: datetime
    ingest_time: datetime
    payload: dict


def simulate(day: datetime, hours: int = 6, seed: int = 11, open_hour: int = 8) -> list[Event]:
    """Return events sorted by ingest time (the order the stream delivers them)."""
    rng = np.random.default_rng(seed)
    start = day.replace(hour=open_hour, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=hours)
    out: list[Event] = []

    def delay() -> timedelta:
        r = rng.random()
        if r < 0.005:
            return timedelta(minutes=float(rng.uniform(18, 30)))  # far too late
        if r < 0.04:
            return timedelta(minutes=float(rng.uniform(1, 4)))  # late but inside allowed lateness
        return timedelta(seconds=float(rng.uniform(0.5, 20)))

    # POS: Poisson arrivals per store per minute
    txn = 0
    t = start
    while t < end:
        for s in STORES:
            rate = 0.35
            if s == SPIKE_STORE and start + timedelta(hours=2) <= t < start + timedelta(hours=2, minutes=30):
                rate = 3.0
            for _ in range(int(rng.poisson(rate))):
                txn += 1
                et = t + timedelta(seconds=float(rng.uniform(0, 60)))
                items = int(rng.integers(1, 8))
                value = round(float(rng.gamma(4.0, 6.0)) + items * 0.5, 2)
                out.append(
                    Event(
                        "pos",
                        s,
                        et,
                        et + delay(),
                        {"txn_id": f"RT{txn:06d}", "store_id": s, "basket_value": value, "items": items},
                    )
                )
        t += timedelta(minutes=1)

    # sensors: one reading per device per minute
    t = start
    while t < end:
        minutes = (t - start).total_seconds() / 60
        for d in DEVICES:
            if d == OFFLINE_DEVICE and 240 <= minutes < 280:
                continue
            temp = -18.0 + float(rng.normal(0, 0.6))
            if d == WARM_DEVICE and minutes >= 180:
                temp = min(-18.0 + (minutes - 180) * 0.25, -4.0) + float(rng.normal(0, 0.3))
            et = t + timedelta(seconds=float(rng.uniform(0, 5)))
            out.append(
                Event(
                    "sensor",
                    d,
                    et,
                    et + delay(),
                    {"device_id": d, "store_id": d.split("-")[0], "temp_c": round(temp, 2)},
                )
            )
        t += timedelta(minutes=1)

    out.sort(key=lambda e: (e.ingest_time, e.key))
    return out
