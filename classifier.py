"""Baseline classifier and urgency heuristic for ticket routing."""

import re
from typing import Literal

# Category keywords (order: Legal > Billing > Technical for tie-breaking)
CATEGORY_RULES = [
    ("Legal", ["lawyer", "legal", "compliance", "gdpr", "contract", "lawsuit", "subpoena"]),
    ("Billing", ["invoice", "payment", "refund", "subscription", "charge", "billing", "credit card"]),
    ("Technical", ["error", "bug", "crash", "login", "api", "broken", "not working", "down", "outage"]),
]

# Urgency signals (regex-friendly)
URGENCY_PATTERN = re.compile(
    r"\b(ASAP|urgent|critical|broken|down|outage|emergency|immediately|"
    r"high priority|P0|as soon as possible)\b",
    re.IGNORECASE,
)

Category = Literal["Billing", "Technical", "Legal"]


def classify_category(text: str) -> Category:
    """Route ticket into Billing, Technical, or Legal by keyword rules."""
    if not text or not text.strip():
        return "Technical"
    lower = text.lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return category  # type: ignore
    return "Technical"


def get_urgency(text: str) -> int:
    """Return urgency score: 0 = low, 1 = high. Used for queue priority."""
    if not text or not text.strip():
        return 0
    return 1 if URGENCY_PATTERN.search(text) else 0


def get_urgency_label(text: str) -> str:
    """Return urgency label for API responses."""
    return "high" if get_urgency(text) == 1 else "low"
