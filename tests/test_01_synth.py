import json

import pandas as pd

from fabricbi import COMPANY
from fabricbi.domain.synth import generate


def test_company_is_fictional():
    assert COMPANY == "Fernhill Grocers"


def test_generator_is_deterministic(tmp_path):
    a = generate(tmp_path / "a", days=7)
    b = generate(tmp_path / "b", days=7)
    assert a.pos_csv.read_bytes() == b.pos_csv.read_bytes()
    assert a.catalog_json.read_bytes() == b.catalog_json.read_bytes()


def test_source_shapes(run):
    src = run.sources
    pos = pd.read_csv(src.pos_csv)
    assert pos.store_id.nunique() == 12
    assert len(pos) > 50_000
    catalog = json.loads(src.catalog_json.read_text())
    items = catalog["products"] if isinstance(catalog, dict) else catalog
    assert len(items) == 40
    tickets = src.tickets_jsonl.read_text().splitlines()
    assert len(tickets) == 120


def test_planted_defects_exist_in_sources(run):
    pos = pd.read_csv(run.sources.pos_csv)
    assert (pos.qty.astype(float) < 0).sum() == 1
    assert pos.duplicated().sum() == 3


def test_tickets_contain_pii_before_silver(run):
    text = run.sources.tickets_jsonl.read_text()
    assert "@" in text
