"""Silver: typed, de-duplicated, validated and privacy-safe tables.

* POS lines: cast types, drop exact duplicate lines, quarantine bad quantities, unknown SKUs and
  unknown stores (rule name kept on each quarantined row).
* Products: parse the catalog JSON, flatten attributes, coerce prices stored as text, and flag
  (not drop) a missing category as `Unassigned` so sales are not lost.
* Freezer readings: cast, de-duplicate, drop physically impossible temperatures.
* Support tickets: personal data (emails, phone numbers) is redacted here, so nothing past bronze
  ever holds raw ticket text.
* Stores and loyalty members come from the mirrored operational database through an internal
  OneLake shortcut, not a copy."""

from __future__ import annotations

import json
import re

import pandas as pd

from fabricbi.coldpath import contracts, quality
from fabricbi.coldpath.mirroring import MirrorReplica
from fabricbi.context import RunContext

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\b\d{3}-\d{4}-\d{4}\b|\b\d{3}-\d{3}-\d{4}\b")


def redact(text: str) -> str:
    return PHONE.sub("[PHONE]", EMAIL.sub("[EMAIL]", text))


class ContractError(RuntimeError):
    pass


def _check(df: pd.DataFrame, name: str) -> None:
    v = contracts.validate(df, contracts.load(name))
    if v:
        raise ContractError(f"{name}: " + "; ".join(f"{x.column}:{x.rule}" for x in v[:5]))


def build_silver(ctx: RunContext) -> dict[str, quality.DqReport]:
    lake = ctx.lake
    reports: dict[str, quality.DqReport] = {}
    with ctx.telemetry.span("silver.build", **{"fabricbi.layer": "silver"}):
        # ---- reference data through shortcuts to the mirrored replica ----
        mirror = MirrorReplica(ctx.lake_root)
        lake.add_shortcut("opdb_stores", mirror.path("stores"), "internal")
        lake.add_shortcut("opdb_customers", mirror.path("customers"), "internal")
        stores = lake.read_shortcut("opdb_stores")
        customers = lake.read_shortcut("opdb_customers")
        ctx.write("silver", "stores", stores, ["mirror.stores"], "shortcut_mirror_stores")
        ctx.write("silver", "customers", customers, ["mirror.customers"], "shortcut_mirror_customers")

        # ---- products ----
        raw = lake.read("bronze", "product_catalog")
        rows, coerced, unassigned = [], 0, 0
        for r in raw.raw_json:
            p = json.loads(r)
            if isinstance(p.get("price"), str):
                coerced += 1
            if not p.get("category"):
                unassigned += 1
            a = p.get("attributes", {})
            rows.append(
                {
                    "sku": p["sku"],
                    "product_name": p["name"],
                    "category": p.get("category") or "Unassigned",
                    "brand": p.get("brand", ""),
                    "list_price": float(p["price"]),
                    "unit_cost": float(p["cost"]),
                    "is_organic": bool(a.get("organic", False)),
                    "is_frozen": bool(a.get("frozen", False)),
                    "allergens": ",".join(a.get("allergens", [])),
                }
            )
        products = pd.DataFrame(rows).drop_duplicates("sku")
        _check(products, "silver.products")
        ctx.write("silver", "products", products, ["bronze.product_catalog"], "nb_silver_products")
        reports["products"] = quality.DqReport(
            "silver.products",
            len(raw),
            len(products),
            0,
            {"warn:price_as_text": coerced, "warn:category_unassigned": unassigned},
        )

        # ---- POS lines ----
        b = lake.read("bronze", "pos_lines")
        before = len(b)
        b = b.drop_duplicates(subset=["txn_id", "line_no", "sku", "qty"])
        dupes = before - len(b)
        rules = [
            quality.in_range("qty", 1, 50),
            quality.references("sku", set(products.sku), "products"),
            quality.references("store_id", set(stores.store_id), "stores"),
            quality.in_range("unit_price", 0.01, 500),
        ]
        good, quar, rep = quality.apply_rules(b, rules, "silver.pos_lines")
        rep.rows_in = before
        if dupes:
            rep.by_rule["dedupe:exact_duplicate"] = dupes
        pos = pd.DataFrame(
            {
                "txn_id": good.txn_id,
                "line_no": good.line_no.astype("int64"),
                "store_id": good.store_id,
                "ts": pd.to_datetime(good.ts),
                "customer_id": good.customer_id.where(good.customer_id != "", None),
                "sku": good.sku,
                "qty": good.qty.astype("int64"),
                "unit_price": good.unit_price.astype("float64"),
                "discount_pct": good.discount_pct.astype("float64"),
            }
        ).reset_index(drop=True)
        _check(pos, "silver.pos_lines")
        ctx.write(
            "silver",
            "pos_lines",
            pos,
            ["bronze.pos_lines", "silver.products", "silver.stores"],
            "nb_silver_pos",
        )
        ctx.write(
            "silver",
            "pos_lines_quarantine",
            quar.drop(columns=["_row_hash"]),
            ["bronze.pos_lines"],
            "nb_silver_pos",
        )
        ctx.telemetry.add("fabricbi.rows.quarantined", rep.quarantined, table="silver.pos_lines")
        reports["pos_lines"] = rep

        # ---- freezer readings ----
        f = lake.read("bronze", "freezer_readings").drop_duplicates(subset=["device_id", "ts"])
        fgood, _fquar, frep = quality.apply_rules(
            f, [quality.in_range("temp_c", -40, 15)], "silver.freezer_readings"
        )
        fz = pd.DataFrame(
            {
                "device_id": fgood.device_id,
                "store_id": fgood.store_id,
                "ts": pd.to_datetime(fgood.ts),
                "temp_c": fgood.temp_c.astype("float64"),
            }
        ).reset_index(drop=True)
        ctx.write("silver", "freezer_readings", fz, ["bronze.freezer_readings"], "nb_silver_freezer")
        reports["freezer_readings"] = frep

        # ---- tickets (PII redacted) ----
        t = lake.read("bronze", "support_tickets")
        tickets = pd.DataFrame(
            {
                "ticket_id": t.ticket_id,
                "store_id": t.store_id,
                "opened": pd.to_datetime(t.opened),
                "channel": t.channel,
                "text_redacted": t.text.map(redact),
            }
        )
        ctx.write("silver", "support_tickets", tickets, ["bronze.support_tickets"], "nb_silver_tickets")
        reports["support_tickets"] = quality.DqReport("silver.support_tickets", len(t), len(tickets), 0)
        ctx.dq_reports.update(reports)
        # nothing reaches gold if a table quarantines more than 2% of its rows; inside the span, so a
        # failed gate marks silver.build as an error with exception.type QualityGateError
        quality.enforce(reports)
    return reports
