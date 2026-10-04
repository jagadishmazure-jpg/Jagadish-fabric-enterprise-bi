"""Semantic model: load, validate, compile queries to SQL, export TMDL.

A query plan is measures + group-by dimensions + filters + order + limit. `compile_sql` turns it
into a star-join SELECT that only joins the dimensions the plan needs, which is what the data
agent executes. `to_tmdl` renders the same model in Tabular Model Definition Language folders so
it can be committed to a Fabric workspace through Git integration or fabric-cicd."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from fabricbi.paths import SEMANTIC_DIR

TMDL_TYPES = {
    "string": "string",
    "int64": "int64",
    "decimal": "decimal",
    "double": "double",
    "boolean": "boolean",
    "dateTime": "dateTime",
}


@dataclass
class Filter:
    dimension: str
    op: str  # = | in | >= | <=
    value: object


@dataclass
class QueryPlan:
    measures: list[str]
    group_by: list[str] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    order_desc: bool = True
    limit: int | None = None
    min_date_key: int | None = None


class SemanticModel:
    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.tables: dict = spec["tables"]
        self.measures = {m["name"]: m for m in spec["measures"]}
        self.dimensions = {d["name"]: d for d in spec["dimensions"]}
        self.relationships = spec["relationships"]

    @classmethod
    def load(cls, path: Path = SEMANTIC_DIR / "retail_sales.yaml") -> SemanticModel:
        return cls(yaml.safe_load(path.read_text()))

    # ---- validation ----
    def validate(self) -> list[str]:
        errs = []
        for r in self.relationships:
            for side in ("from", "to"):
                t, c = r[side].split(".")
                if t not in self.tables or c not in self.tables[t]["columns"]:
                    errs.append(f"relationship {r[side]} does not exist")
        for m in self.measures.values():
            if m["table"] not in self.tables:
                errs.append(f"measure {m['name']} on unknown table {m['table']}")
            for t, c in re.findall(r"(\w+)\[(\w+)\]", m["dax"]):
                if t not in self.tables or c not in self.tables[t]["columns"]:
                    errs.append(f"measure {m['name']} uses missing column {t}.{c}")
        for d in self.dimensions.values():
            t, c = d["column"].split(".")
            if t not in self.tables or c not in self.tables[t]["columns"]:
                errs.append(f"dimension {d['name']} column {d['column']} does not exist")
        syn: dict[str, str] = {}
        for kind, items in (("measure", self.measures.values()), ("dimension", self.dimensions.values())):
            for it in items:
                for s in it["synonyms"]:
                    if s in syn:
                        errs.append(f"synonym {s!r} used by {syn[s]} and {kind} {it['name']}")
                    syn[s] = f"{kind} {it['name']}"
        return errs

    # ---- joins ----
    def join_path(self, fact: str, dim_table: str) -> tuple[str, str] | None:
        if dim_table == fact:
            return None
        for r in self.relationships:
            ft, fc = r["from"].split(".")
            tt, tc = r["to"].split(".")
            if ft == fact and tt == dim_table:
                return (f"{ft}.{fc}", f"{tt}.{tc}")
        raise ValueError(f"no relationship from {fact} to {dim_table}")

    def reachable(self, fact: str, dim: str) -> bool:
        t = self.dimensions[dim]["column"].split(".")[0]
        try:
            self.join_path(fact, t)
            return True
        except ValueError:
            return False

    # ---- SQL ----
    def compile_sql(self, plan: QueryPlan) -> str:
        if not plan.measures:
            raise ValueError("a plan needs at least one measure")
        facts = {self.measures[m]["table"] for m in plan.measures}
        if len(facts) != 1:
            raise ValueError("measures from different fact tables cannot be combined in one query")
        fact = facts.pop()
        dims = [self.dimensions[d] for d in plan.group_by]
        filt_dims = [self.dimensions[f.dimension] for f in plan.filters]
        need = []
        for d in dims + filt_dims:
            t = d["column"].split(".")[0]
            if t != fact and t not in need:
                need.append(t)
        select = [f"{d['column']} AS {d['name']}" for d in dims]
        select += [f'{self.measures[m]["sql"]} AS "{m}"' for m in plan.measures]
        sql = [f"SELECT {', '.join(select)}", f"FROM {fact}"]
        for t in need:
            left, right = self.join_path(fact, t)
            sql.append(f"JOIN {t} ON {left} = {right}")
        where = []
        for f in plan.filters:
            col = self.dimensions[f.dimension]["column"]
            if f.op == "in":
                vals = ", ".join(_lit(v) for v in f.value)
                where.append(f"{col} IN ({vals})")
            else:
                where.append(f"{col} {f.op} {_lit(f.value)}")
        if plan.min_date_key is not None:
            where.append(f"{fact}.date_key >= {int(plan.min_date_key)}")
        if where:
            sql.append("WHERE " + " AND ".join(where))
        if dims:
            sql.append("GROUP BY " + ", ".join(d["column"] for d in dims))
            sql.append(
                f'ORDER BY "{plan.measures[0]}" {"DESC" if plan.order_desc else "ASC"}, {dims[0]["column"]}'
            )
        if plan.limit:
            sql.append(f"LIMIT {int(plan.limit)}")
        return "\n".join(sql)

    # ---- TMDL ----
    def to_tmdl(self) -> dict[str, str]:
        """Return {relative path: TMDL text} for definition/model.tmdl, tables/*.tmdl, relationships.tmdl."""
        files = {
            "definition/model.tmdl": f"model Model\n\tculture: {self.spec['culture']}\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\n"
            + "".join(f"ref table {t}\n" for t in self.tables)
        }
        for t, spec in self.tables.items():
            lines = [f"/// {spec['description']}", f"table {t}", ""]
            for m in (m for m in self.measures.values() if m["table"] == t):
                lines += [
                    f"\t/// {m['description']}",
                    f"\tmeasure '{m['name']}' = {m['dax']}",
                    f"\t\tformatString: {m['format']}",
                    "",
                ]
            for c, typ in spec["columns"].items():
                lines += [f"\tcolumn {c}", f"\t\tdataType: {TMDL_TYPES[typ]}"]
                if c in spec.get("hidden", []):
                    lines.append("\t\tisHidden")
                lines += [f"\t\tsourceColumn: {c}", ""]
            schema, _, name = spec["source"].partition(".")
            lines += [
                f"\tpartition {t} = entity",
                "\t\tmode: directLake",
                "\t\tsource",
                f"\t\t\tentityName: {name}",
                f"\t\t\tschemaName: {schema}",
                "\t\t\texpressionSource: DatabaseQuery",
                "",
            ]
            files[f"definition/tables/{t}.tmdl"] = "\n".join(lines)
        rel = []
        for i, r in enumerate(self.relationships, start=1):
            ft, fc = r["from"].split(".")
            tt, tc = r["to"].split(".")
            rel += [
                f"relationship r{i:02d}_{ft}_{tt}",
                f"\tfromColumn: {ft}.{fc}",
                f"\ttoColumn: {tt}.{tc}",
                "",
            ]
        files["definition/relationships.tmdl"] = "\n".join(rel)
        return files


def _lit(v: object) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, int | float):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"
