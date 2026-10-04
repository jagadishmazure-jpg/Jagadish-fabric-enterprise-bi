"""Data freshness SLOs and error budgets per data product.

Freshness is the age of the newest successful publish of a product's output ports. A product is
`ok` below 80% of its limit, `warning` up to the limit and `breach` beyond it (or if it never
published). Over a series of checks, the error budget is the share of checks allowed to breach
(default 1% for a 99% target); `burn` reports how much of it is used.

Offline the clock is passed in. In Azure the same rule runs as the Log Analytics query in
kql/monitoring/freshness_slo.kql behind an Azure Monitor alert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class FreshnessStatus:
    product: str
    age_hours: float | None
    limit_hours: float
    status: str


def freshness(product: dict, last_publish: datetime | None, now: datetime) -> FreshnessStatus:
    limit = float(product["slo"]["freshness_hours"])
    if last_publish is None:
        return FreshnessStatus(product["name"], None, limit, "breach")
    age = (now - last_publish).total_seconds() / 3600
    status = "ok" if age <= 0.8 * limit else ("warning" if age <= limit else "breach")
    return FreshnessStatus(product["name"], round(age, 2), limit, status)


def error_budget(statuses: list[str], target: float = 0.99) -> dict:
    n = len(statuses)
    bad = sum(s == "breach" for s in statuses)
    allowed = (1 - target) * n
    return {
        "checks": n,
        "breaches": bad,
        "allowed": round(allowed, 2),
        "burn": round(bad / allowed, 2) if allowed else float(bad > 0),
        "met": bad <= allowed,
    }
