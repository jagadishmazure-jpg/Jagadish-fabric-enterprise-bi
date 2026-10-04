"""Lineage graph built from what the pipeline actually ran.

Every step records `(process, inputs, outputs)`. The graph answers the questions a data steward
asks in Microsoft Purview: where did this table come from (`upstream`), what breaks if this
source changes (`downstream`, `impact`), and what does the flow look like (`to_mermaid`). It can
also be exported as OpenLineage-style run events, a format Purview and other catalogs ingest."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LineageGraph:
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (input, process, output)

    def record(self, process: str, inputs: list[str], outputs: list[str]) -> None:
        for i in inputs:
            for o in outputs:
                if (i, process, o) not in self.edges:
                    self.edges.append((i, process, o))

    @property
    def assets(self) -> set[str]:
        return {e[0] for e in self.edges} | {e[2] for e in self.edges}

    def _adj(self, reverse: bool = False) -> dict[str, set[str]]:
        g: dict[str, set[str]] = defaultdict(set)
        for i, _, o in self.edges:
            (g[o] if reverse else g[i]).add(i if reverse else o)
        return g

    def _walk(self, start: str, reverse: bool) -> set[str]:
        g, seen, todo = self._adj(reverse), set(), [start]
        while todo:
            for nxt in g.get(todo.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    def upstream(self, asset: str) -> set[str]:
        return self._walk(asset, reverse=True)

    def downstream(self, asset: str) -> set[str]:
        return self._walk(asset, reverse=False)

    def sources(self) -> set[str]:
        return {a for a in self.assets if not self.upstream(a)}

    def impact(self, asset: str, consumers: dict[str, list[str]]) -> dict[str, list[str]]:
        """Downstream assets plus the data-product consumers that read any of them."""
        down = self.downstream(asset)
        hit = sorted({c for a in down | {asset} for c in consumers.get(a, [])})
        return {"assets": sorted(down), "consumers": hit}

    def has_cycle(self) -> bool:
        return any(a in self.downstream(a) for a in self.assets)

    def to_mermaid(self) -> str:
        def nid(a: str) -> str:
            return a.replace(".", "_").replace("-", "_").replace("/", "_")

        lines = ["flowchart LR"]
        for i, p, o in sorted(self.edges):
            lines.append(f"  {nid(i)}[{i}] -->|{p}| {nid(o)}[{o}]")
        return "\n".join(lines)

    def to_openlineage(self, namespace: str = "fabricbi") -> list[dict]:
        by_proc: dict[str, dict[str, set]] = defaultdict(lambda: {"inputs": set(), "outputs": set()})
        for i, p, o in self.edges:
            by_proc[p]["inputs"].add(i)
            by_proc[p]["outputs"].add(o)
        return [
            {
                "eventType": "COMPLETE",
                "job": {"namespace": namespace, "name": p},
                "inputs": [{"namespace": namespace, "name": n} for n in sorted(v["inputs"])],
                "outputs": [{"namespace": namespace, "name": n} for n in sorted(v["outputs"])],
            }
            for p, v in sorted(by_proc.items())
        ]

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.edges, indent=1))

    @classmethod
    def load(cls, path: Path) -> LineageGraph:
        return cls([tuple(e) for e in json.loads(path.read_text())])
