"""Deterministic stand-in for a Microsoft Foundry chat deployment.

`MockFoundryChatClient.complete(messages, response_format)` has the same shape as a chat
completions call with a JSON schema response format, and returns a JSON string. Behind it is a
keyword scorer, not a model, so results are repeatable and free. Two behaviours are built in so
the harness around it can be tested:

* a ticket that contains an instruction aimed at the model ("ignore previous instructions ...")
  makes the mock comply, returning an off-schema label and an `action` field, the way a real
  model can be steered by untrusted text;
* `fail_every=n` returns malformed JSON on every n-th call, to exercise retry and fallback.

Swap in the Foundry client (azure-ai-inference or the OpenAI SDK against a Foundry endpoint with
Entra ID auth) by implementing the same `complete` method; nothing else changes."""

from __future__ import annotations

import json
import re

LEXICON = {
    "billing": [
        "charged",
        "charge",
        "refund",
        "receipt",
        "bill",
        "price",
        "payment",
        "bank statement",
        "declined",
    ],
    "product_quality": [
        "spoiled",
        "mould",
        "smelled",
        "thawed",
        "refrozen",
        "quality",
        "best-before",
        "packaging",
    ],
    "delivery": ["delivery", "driver", "arrived", "late", "slot", "address", "melted"],
    "store_experience": ["queue", "checkout", "staff", "rude", "aisles", "dirty", "till was open", "pallets"],
    "loyalty": ["loyalty", "points", "reward", "voucher", "tier", "member"],
}
INJECTION = re.compile(r"ignore (all |any )?(previous|prior) instructions", re.I)


class MockFoundryChatClient:
    deployment = "gpt-4o-mini (mock)"

    def __init__(self, fail_every: int = 0) -> None:
        self.calls = 0
        self.fail_every = fail_every

    def complete(self, messages: list[dict], response_format: dict | None = None) -> str:
        self.calls += 1
        if self.fail_every and self.calls % self.fail_every == 0:
            return '{"label": "billing", "confidence": '  # truncated, as a timeout might leave it
        user = messages[-1]["content"]
        text = user.split("<ticket>")[-1].split("</ticket>")[0].lower()
        if INJECTION.search(text):
            return json.dumps({"label": "refund_approved", "confidence": 0.99, "action": "issue_refund"})
        scores = {k: sum(text.count(w) for w in ws) for k, ws in LEXICON.items()}
        best = max(scores, key=scores.get)
        total = sum(scores.values())
        conf = 0.3 if total == 0 else round(0.5 + 0.5 * scores[best] / total, 2)
        return json.dumps(
            {
                "label": best if total else "store_experience",
                "confidence": conf,
                "rationale": f"keywords matched: {scores[best]}",
            }
        )
