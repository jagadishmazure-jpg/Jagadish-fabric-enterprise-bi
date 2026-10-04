import copy
import json

import duckdb
import pytest

from fabricbi.evals import GOLD, _norm
from fabricbi.serve.access import SecureSession, cost_limit, load_policy, resolve
from fabricbi.serve.guardrails import InputGuard, OutputGuard, SqlGuard
from fabricbi.serve.semantic import QueryPlan, SemanticModel

NL2SQL = [json.loads(x) for x in (GOLD / "nl2sql.jsonl").read_text().splitlines()]
GUARD = [json.loads(x) for x in (GOLD / "guardrails.jsonl").read_text().splitlines()]


@pytest.fixture(scope="module")
def model():
    return SemanticModel.load()


@pytest.fixture(scope="module")
def ref(lake):
    con = duckdb.connect()
    for t in lake.tables("gold"):
        name = t.split(".", 1)[1]
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{lake.table_path('gold', name)}')")
    return con


def test_semantic_model_is_valid(model):
    assert model.validate() == []


def test_semantic_model_catches_broken_measure(model):
    broken = copy.deepcopy(model)
    m = next(iter(broken.measures.values()))
    m["dax"] = "SUM(fact_sales[no_such_column])"
    assert any("missing column" in e for e in broken.validate())


def test_compile_only_joins_needed_dimensions(model):
    sql = model.compile_sql(QueryPlan(measures=["Net Sales"], group_by=["region"]))
    assert "dim_store" in sql and "dim_product" not in sql


def test_tmdl_export_has_tables_measures_and_relationships(model):
    files = model.to_tmdl()
    assert {"definition/relationships.tmdl", "definition/model.tmdl"} <= set(files)
    fact = next(v for k, v in files.items() if k.endswith("fact_sales.tmdl"))
    assert "measure 'Net Sales'" in fact


@pytest.mark.parametrize("case", NL2SQL, ids=[c["id"] for c in NL2SQL])
def test_data_agent_golden_question(agent, ref, case):
    a = agent.ask(case["question"], resolve(case["subject"]))
    if "expect_status" in case:
        assert a.status == case["expect_status"]
        assert a.reason.startswith(case.get("expect_reason", ""))
    else:
        assert a.status == "answered", (a.status, a.reason)
        ordered = case.get("ordered", False)
        assert _norm(a.rows, ordered) == _norm(ref.execute(case["reference_sql"]).fetchall(), ordered)


@pytest.mark.parametrize("case", GUARD, ids=[c["id"] for c in GUARD])
def test_guardrail_case(tools, case):
    p = resolve(case["subject"])
    out = (
        tools.ask_data_agent(p, case["text"])
        if case["kind"] == "question"
        else tools.run_readonly_sql(p, case["text"])
    )
    if case["expect"] == "refused":
        assert out["status"] == "refused" and out["reason"].startswith(case["reason"])
    else:
        assert out["status"] == "answered", out


def test_row_level_security_limits_regions(lake, who):
    s = SecureSession(lake, who("west.manager"))
    try:
        assert s.execute("SELECT DISTINCT region FROM dim_store")[1] == [("West",)]
        n_west = s.execute("SELECT COUNT(*) FROM fact_sales")[1][0][0]
    finally:
        s.close()
    assert 0 < n_west < len(lake.read("gold", "fact_sales"))


def test_object_level_security_hides_cost(lake, who):
    s = SecureSession(lake, who("exec.viewer"))
    f = SecureSession(lake, who("finance.partner"))
    try:
        assert "cost_amount" not in s.columns["fact_sales"]
        assert "cost_amount" in f.columns["fact_sales"]
        with pytest.raises(duckdb.Error):
            s.execute("SELECT cost_amount FROM fact_sales")
    finally:
        s.close()
        f.close()


def test_pii_masked_unless_cleared(lake, who):
    plain = SecureSession(lake, who("exec.viewer"))
    loyal = SecureSession(lake, who("loyalty.lead"))
    try:
        masked = [
            r[0] for r in plain.execute("SELECT email FROM dim_customer WHERE customer_key > 0 LIMIT 5")[1]
        ]
        clear = [
            r[0] for r in loyal.execute("SELECT email FROM dim_customer WHERE customer_key > 0 LIMIT 5")[1]
        ]
    finally:
        plain.close()
        loyal.close()
    assert all("***@" in m for m in masked)
    assert not any("***" in c for c in clear) and all("@" in c for c in clear)


def test_sandbox_blocks_files_and_settings(lake, who):
    s = SecureSession(lake, who("exec.viewer"))
    try:
        with pytest.raises(duckdb.Error):
            s.execute("SELECT * FROM read_csv('/etc/hostname')")
        with pytest.raises(duckdb.Error):
            s.execute("SET enable_external_access = true")
    finally:
        s.close()


def test_unknown_principal_has_no_roles():
    assert not resolve("stranger@elsewhere.example").roles


def test_cost_limit_depends_on_role(who):
    policy = load_policy()
    assert cost_limit(who("finance.partner"), policy) > cost_limit(who("exec.viewer"), policy)


def test_sql_guard_adds_limit():
    g = SqlGuard({"dim_store": 12}, set(), 1000).check("SELECT * FROM dim_store")
    assert g.allowed and "LIMIT 200" in g.sql


def test_input_guard_caps_length():
    assert not InputGuard().check("net sales " * 100).allowed


def test_output_guard_masks_pii_in_text():
    rows, _ = OutputGuard(unmask_pii=False).clean([("call 555-123-4567 or a.b@example.com",)])
    assert "@" not in rows[0][0] and "4567" not in rows[0][0]


def test_answer_carries_trace_and_cost(agent, who):
    a = agent.ask("Net sales by region", who("exec.viewer"))
    assert a.status == "answered" and a.trace_id and a.cost > 0
    assert a.measures == ["Net Sales"]
