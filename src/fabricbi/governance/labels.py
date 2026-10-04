"""Sensitivity labels, ordered from least to most restricted (Microsoft Purview style)."""

from __future__ import annotations

LABELS = ("Public", "General", "Confidential", "Highly Confidential")


def rank(label: str) -> int:
    return LABELS.index(label)


def at_most(label: str, clearance: str) -> bool:
    return rank(label) <= rank(clearance)


def strictest(labels) -> str:
    labels = list(labels)
    return max(labels, key=rank) if labels else "Public"


def clearance_for(roles) -> str:
    roles = set(roles)
    if "pii_reader" in roles:
        return "Highly Confidential"
    if "finance" in roles:
        return "Confidential"
    if roles:
        return "General"
    return "Public"
