"""A Purview-style catalog: assets, owners, labels, classifications, lineage, policy checks.

`Catalog.build(lake, lineage)` joins three things: the declared entries in
governance/catalog.yaml, the technical metadata the lake recorded on each write (rows, column
types), and the lineage the pipeline recorded. `check()` returns the policy findings a data
governance team would act on:

* an asset the pipeline wrote that has no catalog entry or no owner;
* a classified (personal data) column on an asset labelled below Highly Confidential;
* a label lower than the strictest input in lineage, without a declared reason (`declassify`);
* an external share of a data product labelled above General."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from fabricbi.governance.labels import LABELS, rank, strictest
from fabricbi.governance.lineage import LineageGraph
from fabricbi.governance.products import load_products
from fabricbi.paths import GOVERNANCE_DIR


@dataclass
class Catalog:
    entries: dict[str, dict]
    classifications: dict[str, str]
    glossary: dict[str, str]
    lineage: LineageGraph = field(default_factory=LineageGraph)
    technical: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        lineage: LineageGraph,
        technical: dict | None = None,
        path: Path = GOVERNANCE_DIR / "catalog.yaml",
    ) -> Catalog:
        spec = yaml.safe_load(path.read_text())
        return cls(spec["assets"], spec["classifications"], spec["glossary"], lineage, technical or {})

    def label(self, asset: str) -> str:
        return self.entries[asset]["label"]

    def check(self) -> list[str]:
        findings = []
        for a in sorted(self.lineage.assets | set(self.technical)):
            e = self.entries.get(a)
            if not e:
                findings.append(f"uncatalogued asset {a}")
                continue
            if not e.get("owner"):
                findings.append(f"{a} has no owner")
            if e.get("label") not in LABELS:
                findings.append(f"{a} has an unknown label {e.get('label')!r}")
        for col, cls_ in self.classifications.items():
            asset = col.rsplit(".", 1)[0]
            if asset in self.entries and rank(self.label(asset)) < rank("Highly Confidential"):
                findings.append(f"{col} is classified as {cls_} but {asset} is labelled {self.label(asset)}")
        for a in sorted(self.lineage.assets):
            if a not in self.entries:
                continue
            ins = [i for i, _, o in self.lineage.edges if o == a and i in self.entries]
            need = strictest(self.label(i) for i in ins)
            if ins and rank(self.label(a)) < rank(need) and not self.entries[a].get("declassify"):
                findings.append(f"{a} is {self.label(a)} but reads {need} input without a declassify reason")
        for p in load_products().values():
            if p["sharing"].get("external_share") and rank(p["sensitivity"]) > rank("General"):
                findings.append(
                    f"data product {p['name']} is {p['sensitivity']} and must not be shared externally"
                )
        return findings

    def search(self, term: str) -> list[str]:
        t = term.lower()
        return sorted(
            a for a, e in self.entries.items() if t in a.lower() or t in e.get("description", "").lower()
        )

    def describe(self, asset: str) -> dict:
        e = self.entries[asset]
        return {
            "asset": asset,
            **e,
            "classified_columns": {
                c.rsplit(".", 1)[1]: v
                for c, v in self.classifications.items()
                if c.rsplit(".", 1)[0] == asset
            },
            "upstream": sorted(self.lineage.upstream(asset)),
            "downstream": sorted(self.lineage.downstream(asset)),
            "technical": self.technical.get(asset, {}),
        }
