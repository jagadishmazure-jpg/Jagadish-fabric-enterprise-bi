"""Run context passed to every pipeline step: where the lake is, and where lineage and telemetry go."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fabricbi.coldpath.lakehouse import Lakehouse
from fabricbi.governance.lineage import LineageGraph
from fabricbi.observability.telemetry import Telemetry


@dataclass
class RunContext:
    lake_root: Path
    run_id: str = "run-0001"
    logical_time: str = ""
    lineage: LineageGraph = field(default_factory=LineageGraph)
    telemetry: Telemetry = field(default_factory=Telemetry)
    dq_reports: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.lake_root = Path(self.lake_root)
        self.lake = Lakehouse(self.lake_root)

    def write(self, layer: str, table: str, df, inputs: list[str], process: str):
        self.lake.write(layer, table, df, run_id=self.run_id, logical_time=self.logical_time)
        self.lineage.record(process, inputs, [f"{layer}.{table}"])
        self.telemetry.add(
            "fabricbi.rows.written", len(df), table=f"{layer}.{table}", **{"fabricbi.layer": layer}
        )
