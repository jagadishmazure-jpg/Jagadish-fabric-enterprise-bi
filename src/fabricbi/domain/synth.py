"""Deterministic synthetic data for a fictional grocery chain (Fernhill Grocers).

Everything is generated from one seed so tests, evals and the demo see identical data. The
generator writes the *source systems*, not the lake: a POS export (CSV), a product catalog (JSON
with nested attributes and some messy values), freezer telemetry (CSV for history, events for the
hot path), support tickets (free text with personal data in it) and an operational database of
stores and loyalty members (rows plus a change log for mirroring).

A handful of defects are planted on purpose so the data quality layer has something to catch:
duplicate POS lines, a negative quantity, an unknown SKU, a catalog price stored as text and a
product with no category."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
CALENDAR_START = datetime(2025, 3, 3)  # a Monday; synthetic calendar only
REGIONS = ("North", "South", "East", "West")
TOWNS = {
    "North": ("Alder Falls", "Birchmoor", "Cedar Point"),
    "South": ("Dunmore", "Elmstead", "Fairhollow"),
    "East": ("Glenbrook", "Hazelton", "Ivydale"),
    "West": ("Juniper Bay", "Kestrel Ridge", "Larchwood"),
}
CATEGORIES = {
    "Dairy": (
        ["Whole Milk", "Greek Yogurt", "Cheddar Block", "Butter", "Oat Milk", "Cottage Cheese", "Cream"],
        3.5,
    ),
    "Frozen": (
        [
            "Ice Cream Tub",
            "Frozen Peas",
            "Pizza Margherita",
            "Fish Fillets",
            "Berry Mix",
            "Waffles",
            "Dumplings",
        ],
        5.0,
    ),
    "Produce": (["Bananas", "Apples", "Spinach", "Tomatoes", "Avocados", "Carrots", "Blueberries"], 2.8),
    "Bakery": (["Sourdough Loaf", "Bagels", "Croissants", "Rye Bread", "Muffins", "Tortillas"], 4.0),
    "Pantry": (["Pasta", "Basmati Rice", "Olive Oil", "Peanut Butter", "Canned Beans", "Oats", "Honey"], 4.5),
    "Beverages": (["Sparkling Water", "Orange Juice", "Cold Brew", "Green Tea", "Cola", "Kombucha"], 3.0),
}
BRANDS = ("Fernhill Own", "Meadowlark", "Copperpot", "Bluewater", "Sunfield")
TIERS = ("bronze", "silver", "gold")
TICKET_TEMPLATES = {
    "billing": [
        "I was charged twice for my groceries at the {town} store, please refund the duplicate charge. Reach me at {email}.",
        "My receipt shows a price higher than the shelf tag for {product}. Can someone correct the bill? Phone {phone}.",
        "The card payment went through but the till said declined, now my bank statement has an extra charge.",
    ],
    "product_quality": [
        "The {product} I bought was spoiled and smelled off even before the best-before date.",
        "Found mould on the {product} from the {town} branch, this is the second time this month.",
        "{product} was thawed and refrozen, the packaging was soft and wet. Quality is not acceptable.",
    ],
    "delivery": [
        "My home delivery arrived three hours late and the frozen items had melted. Contact {email}.",
        "The driver left my order at the wrong address, missing delivery for order with {product}.",
        "Delivery slot was cancelled without notice, nobody called me on {phone}.",
    ],
    "store_experience": [
        "The checkout queue at {town} was very long and only one till was open.",
        "Staff at the {town} store were rude when I asked where to find {product}.",
        "Aisles were blocked with pallets and the store floor was dirty during my visit.",
    ],
    "loyalty": [
        "My loyalty points from last week never showed up in the app. Member email {email}.",
        "I cannot redeem my reward voucher at the till, the loyalty card keeps getting rejected.",
        "Please update my loyalty tier, I spent enough to reach gold but I am still listed as silver.",
    ],
}


@dataclass(frozen=True)
class SourceFiles:
    """Paths of everything the generator wrote, keyed the way the ingest layer expects."""

    pos_csv: Path
    catalog_json: Path
    sensor_csv: Path
    tickets_jsonl: Path
    ticket_labels_jsonl: Path
    opdb: Path
    days: int
    batch_cutoff: datetime


def _stores() -> pd.DataFrame:
    rows = []
    n = 1
    for region in REGIONS:
        for town in TOWNS[region]:
            rows.append(
                {
                    "store_id": f"S{n:03d}",
                    "store_name": f"Fernhill {town}",
                    "city": town,
                    "region": region,
                    "square_meters": 900 + 150 * (n % 5),
                }
            )
            n += 1
    return pd.DataFrame(rows)


def _products(rng: np.random.Generator) -> list[dict]:
    out = []
    n = 1
    for cat, (names, base) in CATEGORIES.items():
        for name in names:
            price = round(base * float(rng.uniform(0.6, 1.8)), 2)
            out.append(
                {
                    "sku": f"P{n:04d}",
                    "name": name,
                    "category": cat,
                    "brand": BRANDS[n % len(BRANDS)],
                    "price": price,
                    "cost": round(price * float(rng.uniform(0.55, 0.75)), 2),
                    "attributes": {
                        "organic": bool(n % 4 == 0),
                        "allergens": ["milk"] if cat == "Dairy" else (["gluten"] if cat == "Bakery" else []),
                        "frozen": cat == "Frozen",
                    },
                }
            )
            n += 1
    # planted defects: one price stored as text, one product missing its category
    out[3]["price"] = f"{out[3]['price']}"
    out[-1] = {k: v for k, v in out[-1].items() if k != "category"}
    return out


def _customers(rng: np.random.Generator, stores: pd.DataFrame, n: int = 300) -> pd.DataFrame:
    first = ["Ava", "Ben", "Cleo", "Dev", "Esme", "Finn", "Gita", "Hugo", "Iris", "Jon", "Kai", "Lena"]
    rows = []
    for i in range(1, n + 1):
        name = first[i % len(first)]
        rows.append(
            {
                "customer_id": f"C{i:05d}",
                "first_name": name,
                "email": f"{name.lower()}.{i}@example.com",
                "phone": f"555-01{i % 100:02d}-{1000 + i:04d}",
                "home_store_id": stores.store_id.iloc[int(rng.integers(0, len(stores)))],
                "tier": TIERS[int(rng.integers(0, 3))],
            }
        )
    return pd.DataFrame(rows)


def _pos(rng, stores, products, customers, days: int) -> pd.DataFrame:
    skus = [p["sku"] for p in products]
    prices = {p["sku"]: float(p["price"]) for p in products}
    cat_of = {p["sku"]: p.get("category", "Pantry") for p in products}
    cat_weight = {"Dairy": 1.3, "Produce": 1.4, "Bakery": 1.0, "Frozen": 0.9, "Pantry": 1.0, "Beverages": 1.1}
    w = np.array([cat_weight[cat_of[s]] for s in skus])
    w = w / w.sum()
    dow_factor = [0.85, 0.9, 0.95, 1.0, 1.2, 1.45, 1.25]
    rows = []
    txn = 0
    for d in range(days):
        day = CALENDAR_START + timedelta(days=d)
        trend = 1.0 + 0.002 * d
        for _, st in stores.iterrows():
            size = st.square_meters / 1200
            lam = 26 * dow_factor[day.weekday()] * trend * size
            for _ in range(int(rng.poisson(lam))):
                txn += 1
                ts = day + timedelta(hours=8, minutes=int(rng.integers(0, 13 * 60)))
                cust = (
                    customers.customer_id.iloc[int(rng.integers(0, len(customers)))]
                    if rng.random() < 0.6
                    else ""
                )
                for line, sku in enumerate(rng.choice(skus, size=int(rng.integers(1, 6)), p=w), start=1):
                    qty = int(rng.integers(1, 4))
                    disc = 0.1 if rng.random() < 0.08 else 0.0
                    rows.append(
                        {
                            "txn_id": f"T{txn:07d}",
                            "line_no": line,
                            "store_id": st.store_id,
                            "ts": ts.isoformat(timespec="minutes"),
                            "customer_id": cust,
                            "sku": sku,
                            "qty": qty,
                            "unit_price": prices[sku],
                            "discount_pct": disc,
                        }
                    )
    df = pd.DataFrame(rows)
    # planted defects
    dupes = df.iloc[[10, 11, 12]].copy()
    bad_qty = df.iloc[[20]].copy().assign(line_no=99, qty=-2)
    bad_sku = df.iloc[[30]].copy().assign(line_no=98, sku="P9999")
    return pd.concat([df, dupes, bad_qty, bad_sku], ignore_index=True)


def _sensors(rng, stores, days: int) -> pd.DataFrame:
    rows = []
    for _, st in stores.iterrows():
        for k in (1, 2):
            dev = f"{st.store_id}-FZ{k}"
            for d in range(days):
                day = CALENDAR_START + timedelta(days=d)
                for h in range(0, 24, 1):  # hourly history; the hot path carries minute-level events
                    temp = -18.0 + float(rng.normal(0, 0.8))
                    if dev == "S004-FZ1" and d == days - 3 and 13 <= h <= 16:
                        temp = -9.0 + float(rng.normal(0, 0.5))  # a warm afternoon in history
                    rows.append(
                        {
                            "device_id": dev,
                            "store_id": st.store_id,
                            "ts": (day + timedelta(hours=h)).isoformat(timespec="minutes"),
                            "temp_c": round(temp, 2),
                        }
                    )
    return pd.DataFrame(rows)


def _tickets(rng, stores, products, customers, n: int = 120) -> tuple[list[dict], list[dict]]:
    tickets, labels = [], []
    cats = list(TICKET_TEMPLATES)
    names = [p["name"] for p in products]
    for i in range(1, n + 1):
        cat = cats[i % len(cats)]
        tmpl = TICKET_TEMPLATES[cat][int(rng.integers(0, len(TICKET_TEMPLATES[cat])))]
        st = stores.iloc[int(rng.integers(0, len(stores)))]
        cu = customers.iloc[int(rng.integers(0, len(customers)))]
        text = tmpl.format(
            town=st.city,
            product=names[int(rng.integers(0, len(names)))].lower(),
            email=cu.email,
            phone=cu.phone,
        )
        tickets.append(
            {
                "ticket_id": f"K{i:05d}",
                "store_id": st.store_id,
                "opened": (CALENDAR_START + timedelta(days=int(rng.integers(0, 60)))).date().isoformat(),
                "channel": ["app", "email", "phone"][i % 3],
                "text": text,
            }
        )
        labels.append({"ticket_id": f"K{i:05d}", "label": cat})
    return tickets, labels


def generate(out_dir: Path, days: int = 56, seed: int = SEED) -> SourceFiles:
    """Write every synthetic source into `out_dir` (the 'source systems' folder)."""
    from fabricbi.coldpath.mirroring import OperationalDb  # local import: avoids a cycle

    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    stores = _stores()
    products = _products(rng)
    customers = _customers(rng, stores)
    pos = _pos(rng, stores, products, customers, days)
    sensors = _sensors(rng, stores, days)
    tickets, labels = _tickets(rng, stores, products, customers)

    files = SourceFiles(
        pos_csv=out_dir / "pos_export.csv",
        catalog_json=out_dir / "product_catalog.json",
        sensor_csv=out_dir / "freezer_history.csv",
        tickets_jsonl=out_dir / "support_tickets.jsonl",
        ticket_labels_jsonl=out_dir / "support_ticket_labels.jsonl",
        opdb=out_dir / "operational.db",
        days=days,
        batch_cutoff=CALENDAR_START + timedelta(days=days),
    )
    pos.to_csv(files.pos_csv, index=False)
    files.catalog_json.write_text(
        json.dumps({"retailer": "Fernhill Grocers", "products": products}, indent=1)
    )
    sensors.to_csv(files.sensor_csv, index=False)
    files.tickets_jsonl.write_text("".join(json.dumps(t) + "\n" for t in tickets))
    files.ticket_labels_jsonl.write_text("".join(json.dumps(t) + "\n" for t in labels))

    if files.opdb.exists():
        files.opdb.unlink()
    db = OperationalDb(files.opdb)
    db.seed(stores, customers)
    # a few operational changes after the initial load, so mirroring has updates and a delete
    db.update("customers", "C00007", {"tier": "gold"})
    db.update("stores", "S005", {"store_name": "Fernhill Elmstead Market"})
    db.delete("customers", "C00300")
    db.close()
    return files
