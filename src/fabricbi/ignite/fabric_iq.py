"""Fabric IQ-style tool: one business question, one caller, the semantic model.

Fabric IQ's data agents answer natural-language questions from governed business definitions.
The Fabric IQ post says Fabric permissions stay with the caller, including OneLake roles that
can limit rows and columns, and the Fabric data-agent post says each question respects
row-level and column-level security on the underlying data. `FabricIqTool` is that tool
offline. It does not grant the agent its own view of the lake: it resolves the caller and
asks the existing data agent, which compiles the semantic model and runs inside that caller's
secure session.
"""

from __future__ import annotations

from fabricbi.coldpath.lakehouse import Lakehouse
from fabricbi.serve.access import resolve
from fabricbi.serve.data_agent import DataAgent

TOOL_NAME = "ask_business_question"


def tool_spec() -> dict:
    return {
        "name": TOOL_NAME,
        "description": (
            "Answer a business question over the retail semantic model for the signed-in caller. "
            "Rows are limited to that caller's regions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "caller": {
                    "type": "string",
                    "description": "Signed-in subject, for example west.manager@fernhill.example.",
                },
                "question": {"type": "string", "description": "A business question in plain language."},
            },
            "required": ["caller", "question"],
            "additionalProperties": False,
        },
    }


class FabricIqTool:
    def __init__(self, lake: Lakehouse, agent: DataAgent | None = None) -> None:
        self.agent = agent or DataAgent(lake)

    def spec(self) -> dict:
        return tool_spec()

    def call(self, caller: str, question: str) -> dict:
        principal = resolve(caller)
        answer = self.agent.ask(question, principal)
        body = answer.to_dict()
        body["tool"] = TOOL_NAME
        body["caller"] = principal.subject
        body["regions"] = list(principal.all_regions)
        return body
