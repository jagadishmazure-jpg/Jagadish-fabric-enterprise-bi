"""OpenTelemetry-shaped telemetry with no SDK dependency.

Spans and metrics use OpenTelemetry names and attribute conventions (`db.system`,
`db.operation.name`, `fabricbi.layer`, ...) so the same records can be sent to Application Insights
through the Azure Monitor OpenTelemetry exporter once a workspace exists. Offline, they stay in
memory and can be written as JSON lines, which is what tests and the demo read.

Metric names:
  fabricbi.rows.written        counter    rows written per table
  fabricbi.rows.quarantined    counter    rows rejected by data quality rules
  fabricbi.step.duration       histogram  milliseconds per pipeline step
  fabricbi.agent.queries       counter    data agent questions, by outcome
  fabricbi.hotpath.late_events counter    events that arrived after the watermark"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: str | None
    attributes: dict
    start_ns: int
    end_ns: int = 0
    status: str = "unset"

    @property
    def duration_ms(self) -> float:
        return (self.end_ns - self.start_ns) / 1e6


@dataclass
class Telemetry:
    service: str = "fabric-enterprise-bi"
    spans: list[Span] = field(default_factory=list)
    counters: dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    histograms: dict[tuple, list[float]] = field(default_factory=lambda: defaultdict(list))
    _stack: list[Span] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @contextmanager
    def span(self, name: str, **attrs):
        parent = self._stack[-1] if self._stack else None
        sp = Span(
            name,
            self.trace_id,
            uuid.uuid4().hex[:16],
            parent.span_id if parent else None,
            dict(attrs),
            time.perf_counter_ns(),
        )
        self._stack.append(sp)
        try:
            yield sp
            sp.status = "ok"
        except Exception as exc:
            sp.status = "error"
            sp.attributes["exception.type"] = type(exc).__name__
            raise
        finally:
            sp.end_ns = time.perf_counter_ns()
            self._stack.pop()
            self.spans.append(sp)
            self.record("fabricbi.step.duration", sp.duration_ms, step=name)

    def add(self, metric: str, value: float = 1, **attrs) -> None:
        self.counters[(metric, tuple(sorted(attrs.items())))] += value

    def record(self, metric: str, value: float, **attrs) -> None:
        self.histograms[(metric, tuple(sorted(attrs.items())))].append(value)

    def counter(self, metric: str, **attrs) -> float:
        want = set(attrs.items())
        return sum(v for (m, a), v in self.counters.items() if m == metric and want <= set(a))

    def export_jsonl(self, path: Path) -> int:
        lines = [
            json.dumps(
                {
                    "type": "span",
                    "service": self.service,
                    "name": s.name,
                    "trace_id": s.trace_id,
                    "span_id": s.span_id,
                    "parent_id": s.parent_id,
                    "duration_ms": round(s.duration_ms, 3),
                    "status": s.status,
                    "attributes": s.attributes,
                },
                default=str,
            )
            for s in self.spans
        ]
        lines += [
            json.dumps({"type": "counter", "name": m, "attributes": dict(a), "value": v})
            for (m, a), v in self.counters.items()
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        return len(lines)
