"""A Fabric app page, offline, bound to the retail semantic model.

Fabric apps are generally available. They connect to an existing semantic model and keep that
model's access controls, instead of copying measures into the app. `RetailReviewApp` is that
shape without Rayfin or a Fabric tenant: each page is a query plan over the semantic model, and
the SQL runs in the caller's secure session (row-level security by region, hidden finance
columns, masked personal data).
"""

from __future__ import annotations

from dataclasses import dataclass

from fabricbi.coldpath.lakehouse import Lakehouse
from fabricbi.serve.access import Principal, SecureSession, load_policy
from fabricbi.serve.semantic import QueryPlan, SemanticModel


@dataclass(frozen=True)
class AppPage:
    page_id: str
    title: str
    measures: tuple[str, ...]
    group_by: tuple[str, ...]


@dataclass
class PageView:
    page_id: str
    title: str
    caller: str
    regions: tuple[str, ...]
    measures: tuple[str, ...]
    columns: list[str]
    rows: list[tuple]
    sql: str


# Pages are definitions on the semantic model, not handwritten SQL.
PAGES = (
    AppPage("regional_review", "Regional sales review", ("Net Sales",), ("region",)),
    AppPage("category_mix", "Category mix", ("Net Sales", "Units"), ("category",)),
    AppPage("store_sales", "Sales by store", ("Net Sales",), ("store",)),
)


class RetailReviewApp:
    """Stand-in for a Fabric app whose screens read `sm_retail_sales`."""

    def __init__(self, lake: Lakehouse, model: SemanticModel | None = None) -> None:
        self.lake = lake
        self.model = model or SemanticModel.load()
        self.policy = load_policy()

    def pages(self) -> tuple[AppPage, ...]:
        return PAGES

    def open_page(self, page_id: str, principal: Principal) -> PageView:
        page = next((p for p in PAGES if p.page_id == page_id), None)
        if page is None:
            raise KeyError(page_id)
        if not principal.roles:
            raise PermissionError("no_role")
        for name in page.measures:
            if name not in self.model.measures:
                raise KeyError(name)
        plan = QueryPlan(measures=list(page.measures), group_by=list(page.group_by))
        sql = self.model.compile_sql(plan)
        session = SecureSession(self.lake, principal, self.policy)
        try:
            columns, rows = session.execute(sql)
        finally:
            session.close()
        return PageView(
            page_id=page.page_id,
            title=page.title,
            caller=principal.subject,
            regions=principal.all_regions,
            measures=page.measures,
            columns=columns,
            rows=rows,
            sql=sql,
        )
