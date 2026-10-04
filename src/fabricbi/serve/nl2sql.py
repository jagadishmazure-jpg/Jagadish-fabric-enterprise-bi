"""Natural language to a semantic query plan, then to SQL.

`MockNl2SqlModel` stands in for a Foundry model prompted with the semantic model (measure and
dimension names, descriptions and synonyms). It is a deterministic parser, so the eval set can
check exact answers. It understands:

  measures       any measure synonym ("revenue", "average basket", "warm hours", ...)
  group by       "by X", "per X", "for each X", "top N X", "which X"
  filters        region, category, city and brand names; "weekend" / "weekdays"; loyalty tiers
  time           "last N days" or "last N weeks", counted back from the newest sales day
  ordering       "top N", "bottom N", "lowest", "least"

If it cannot find a measure it returns `CANNOT_ANSWER` instead of guessing. Like a real model it
can be steered: a question that says "run this sql: ..." makes it return that SQL verbatim, which
is why the SQL guard exists (the input guard normally stops that phrasing first)."""

from __future__ import annotations

import re

from fabricbi.serve.semantic import Filter, QueryPlan, SemanticModel

CANNOT = "-- CANNOT_ANSWER"
REGIONS = ("north", "south", "east", "west")
CATEGORIES = ("dairy", "frozen", "produce", "bakery", "pantry", "beverages")
TIERS = ("bronze", "silver", "gold")
NUM = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _int(tok: str) -> int | None:
    return int(tok) if tok.isdigit() else NUM.get(tok)


class MockNl2SqlModel:
    name = "nl2sql-mock"

    def __init__(
        self, model: SemanticModel, cities: tuple[str, ...] = (), brands: tuple[str, ...] = ()
    ) -> None:
        self.model = model
        self.cities = tuple(c.lower() for c in cities)
        self.brands = tuple(b.lower() for b in brands)

    def _find(self, q: str, items: dict) -> list[tuple[int, str]]:
        hits = []
        for name, it in items.items():
            for s in sorted(it["synonyms"], key=len, reverse=True):
                m = re.search(rf"\b{re.escape(s)}\b", q)
                if m:
                    hits.append((m.start(), name, len(s)))
                    break
        # drop hits that sit inside a longer hit ("sales" inside "net sales" is fine, same measure)
        hits.sort(key=lambda h: (h[0], -h[2]))
        out, end = [], -1
        for start, name, ln in hits:
            if start >= end:
                out.append((start, name))
                end = start + ln
        return out

    def plan(self, question: str, max_date_key: int | None = None) -> QueryPlan | None:
        q = " " + question.lower().replace("?", " ").replace(",", " ") + " "
        measures = [n for _, n in self._find(q, self.model.measures)]
        if not measures:
            return None
        fact = self.model.measures[measures[0]]["table"]
        measures = [m for m in measures if self.model.measures[m]["table"] == fact]
        plan = QueryPlan(measures=measures)

        # group by: "by X", "per X", "each X", "which X", "top N X"
        dims = self._find(q, self.model.dimensions)
        for pos, name in dims:
            before = q[max(0, pos - 18) : pos]
            if (
                re.search(r"\b(by|per|each|which|across|top \w+|bottom \w+|for every)\s+$", before)
                and name not in plan.group_by
            ):
                plan.group_by.append(name)

        # filters on dimension values
        regions = [
            r.title()
            for r in REGIONS
            if re.search(rf"\b{r}(ern)?\b(?! of)", q) and "region" not in plan.group_by
        ]
        if regions:
            plan.filters.append(Filter("region", "in", regions))
        cats = [c.title() for c in CATEGORIES if re.search(rf"\b{c}\b", q)]
        if cats and "category" not in plan.group_by:
            plan.filters.append(Filter("category", "in", cats))
        cities = [c.title() for c in self.cities if c in q]
        if cities and "city" not in plan.group_by:
            plan.filters.append(Filter("city", "in", cities))
        brands = [b.title() for b in self.brands if b in q]
        if brands and "brand" not in plan.group_by:
            plan.filters.append(Filter("brand", "in", [b for b in brands]))
        tiers = [t for t in TIERS if re.search(rf"\b{t} (members?|tier|customers?)\b", q)]
        if tiers and "tier" not in plan.group_by:
            plan.filters.append(Filter("tier", "in", tiers))
        if re.search(r"\bweekends?\b", q):
            plan.filters.append(Filter("day_of_week", "in", ["Saturday", "Sunday"]))
        elif re.search(r"\bon weekdays\b", q):
            plan.filters.append(
                Filter("day_of_week", "in", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            )

        # time window
        m = re.search(r"\b(?:last|past) (\w+) (day|days|week|weeks)\b", q) or re.search(
            r"\b(?:last|past) (week)\b", q
        )
        if m and max_date_key is not None:
            from datetime import datetime, timedelta

            n = 1 if m.group(1) == "week" else _int(m.group(1)) or 0
            unit = "week" if m.group(1) == "week" else m.group(2)
            days = n * 7 if unit.startswith("week") else n
            newest = datetime.strptime(str(max_date_key), "%Y%m%d")
            plan.min_date_key = int((newest - timedelta(days=days - 1)).strftime("%Y%m%d"))

        # ordering and limits
        m = re.search(r"\b(top|bottom) (\w+)\b", q)
        if m and _int(m.group(2)):
            plan.limit = _int(m.group(2))
            plan.order_desc = m.group(1) == "top"
        elif re.search(r"\b(lowest|least|worst|fewest)\b", q):
            plan.order_desc, plan.limit = False, 1 if plan.group_by else None
        elif re.search(r"\b(highest|most|best|biggest)\b", q) and plan.group_by:
            plan.limit = 1
        # dimensions must be reachable from the fact table
        plan.group_by = [d for d in plan.group_by if self.model.reachable(fact, d)]
        plan.filters = [f for f in plan.filters if self.model.reachable(fact, f.dimension)]
        return plan

    def generate(self, question: str, max_date_key: int | None = None) -> str:
        m = re.search(r"run (?:this|the following) sql:\s*(.+)$", question, re.I | re.S)
        if m:
            return m.group(1).strip()
        plan = self.plan(question, max_date_key)
        return CANNOT if plan is None else self.model.compile_sql(plan)
