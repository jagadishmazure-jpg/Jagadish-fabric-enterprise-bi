"""End-to-end run: sources -> ingest -> store -> process -> enrich -> serve -> govern.

`run_all(workdir)` executes every stage in order on synthetic data and returns a `PipelineRun`
with the run context (lake, lineage, telemetry), the hot-path result, the forecast and the ticket
classifications. Tests share one run per session; the demo prints what each stage did."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from fabricbi.coldpath.bronze import BronzeIngest
from fabricbi.coldpath.gold import build_gold
from fabricbi.coldpath.gold import write_contracted as write_gold
from fabricbi.coldpath.mirroring import MirrorReplica, OperationalDb
from fabricbi.coldpath.silver import build_silver
from fabricbi.context import RunContext
from fabricbi.domain.synth import SourceFiles, generate
from fabricbi.enrich import forecast as fc
from fabricbi.enrich.foundry_mock import MockFoundryChatClient
from fabricbi.enrich.tickets import Classification, classify
from fabricbi.hotpath import stream, windows
from fabricbi.lambda_view import serving_view


@dataclass
class PipelineRun:
    ctx: RunContext
    sources: SourceFiles
    hot: windows.HotPathResult
    forecast: fc.ForecastResult
    tickets: list[Classification]
    mirror_lag: int

    @property
    def lake(self):
        return self.ctx.lake


def run_hot_path(ctx: RunContext, cutoff: datetime) -> windows.HotPathResult:
    with ctx.telemetry.span("hotpath.eventstream", **{"messaging.system": "eventhubs"}):
        events = stream.simulate(cutoff)
        hot = windows.run(events)
    eh = ctx.lake_root / "eh_retail"
    eh.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(hot.sales_windows).to_parquet(eh / "sales_windows.parquet", index=False)
    pd.DataFrame(hot.sensor_windows).to_parquet(eh / "sensor_windows.parquet", index=False)
    pd.DataFrame([a.__dict__ for a in hot.alerts]).to_parquet(eh / "hot_alerts.parquet", index=False)
    for out in ("eventhouse.sales_windows", "eventhouse.hot_alerts"):
        ctx.lineage.record("eventstream_pos", ["source.event_hubs.pos"], [out])
    for out in ("eventhouse.sensor_windows", "eventhouse.hot_alerts"):
        ctx.lineage.record("eventstream_freezers", ["source.iot_hub.freezers"], [out])
    ctx.telemetry.add("fabricbi.hotpath.late_events", len(hot.late_events))
    return hot


def run_all(workdir: Path, days: int = 56) -> PipelineRun:
    workdir = Path(workdir)
    src = generate(workdir / "sources", days=days)
    ctx = RunContext(workdir / "lake", run_id="run-0001", logical_time=src.batch_cutoff.isoformat())

    # ingest: copy jobs into bronze, mirroring for the operational database
    BronzeIngest(ctx).run(src)
    db = OperationalDb(src.opdb)
    mirror = MirrorReplica(ctx.lake_root)
    with ctx.telemetry.span("mirroring.sync", **{"db.system": "sqlite"}):
        mirror.sync(db)
    lag = mirror.lag(db)
    db.close()
    ctx.lineage.record("mirroring_opdb", ["source.opdb.stores"], ["mirror.stores"])
    ctx.lineage.record("mirroring_opdb", ["source.opdb.customers"], ["mirror.customers"])

    # process: silver and gold
    build_silver(ctx)
    build_gold(ctx, through_day=pd.Timestamp(src.batch_cutoff))

    # enrich: tickets (Foundry, mocked) and the demand forecast
    client = MockFoundryChatClient()
    t = ctx.lake.read("silver", "support_tickets")
    with ctx.telemetry.span("enrich.tickets", **{"gen_ai.system": "foundry-mock"}):
        results = [classify(r.ticket_id, r.text_redacted, client) for r in t.itertuples()]
    sk = dict(
        zip(
            ctx.lake.read("gold", "dim_store").store_id,
            ctx.lake.read("gold", "dim_store").store_key,
            strict=True,
        )
    )
    fact_ticket = pd.DataFrame(
        {
            "ticket_id": t.ticket_id,
            "date_key": t.opened.dt.strftime("%Y%m%d").astype("int64"),
            "store_key": t.store_id.map(sk).astype("int64"),
            "channel": t.channel,
            "category": [r.label for r in results],
            "confidence": [float(r.confidence) for r in results],
            "needs_review": [bool(r.needs_review) for r in results],
        }
    )
    write_gold(
        ctx,
        "fact_ticket",
        fact_ticket,
        ["silver.support_tickets", "ml.ticket_classifier", "gold.dim_store"],
        "enrich_ticket_classifier",
    )

    with ctx.telemetry.span("enrich.forecast", **{"ml.framework": "scikit-learn"}):
        res = fc.train_and_backtest(
            ctx.lake.read("gold", "agg_daily_sales"), ctx.lake.read("gold", "dim_store")
        )
    ctx.lineage.record("train_demand_forecast", ["gold.agg_daily_sales"], ["ml.demand_forecast"])
    write_gold(
        ctx,
        "forecast_sales",
        res.predictions.astype({"lag7": "float64"}),
        ["gold.agg_daily_sales", "ml.demand_forecast"],
        "score_demand_forecast",
    )

    # hot path and the Lambda serving view
    hot = run_hot_path(ctx, src.batch_cutoff)
    view = serving_view(
        ctx.lake.read("gold", "agg_daily_sales"),
        ctx.lake.read("gold", "dim_store"),
        hot.sales_windows,
        src.batch_cutoff,
    )
    write_gold(
        ctx,
        "serving_sales_daily",
        view,
        ["gold.agg_daily_sales", "gold.dim_store", "eventhouse.sales_windows"],
        "lambda_serving_view",
    )

    ctx.lineage.record("index_docs", ["docs.repository"], ["index.docs_vector"])
    ctx.lineage.save(ctx.lake_root / "_lineage.json")
    (ctx.lake_root / "_dq_reports.json").write_text(
        json.dumps({k: v.__dict__ for k, v in ctx.dq_reports.items()}, indent=1, default=str)
    )
    return PipelineRun(ctx, src, hot, res, results, lag)
