from __future__ import annotations

import re

from support_copilot.models import Classification, Intent, Ticket, Urgency

INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.DAMAGED: (
        "damaged",
        "crushed",
        "bent",
        "gouge",
        "broken",
        "dented",
        "smashed",
        "box was",
    ),
    Intent.WRONG_ITEM: ("wrong size", "wrong item", "not what i ordered", "sent the wrong"),
    Intent.MISSING_PARTS: ("missing", "wasn't in the box", "not in the box", "charger", "incomplete"),
    Intent.BILLING: (
        "charged twice",
        "duplicate",
        "double charge",
        "billed twice",
        "invoice",
        "statement",
    ),
    Intent.WARRANTY: (
        "warranty",
        "battery",
        "motor",
        "controller",
        "defect",
        "serial",
        "not charging",
    ),
    Intent.CANCEL: ("cancel", "cancellation", "stop the order", "don't need"),
    Intent.REFUND: ("refund", "money back", "want my money"),
    Intent.RETURN: ("return", "send back", "send them back", "return label"),
    Intent.ORDER_STATUS: (
        "where is",
        "where's",
        "tracking",
        "shipped",
        "delivery",
        "eta",
        "has my order",
        "in transit",
        "when should i expect",
        "stuck",
    ),
    Intent.PRODUCT_QUESTION: (
        "range",
        "spec",
        "how far",
        "eco mode",
        "not a complaint",
        "realistic",
    ),
}

CRITICAL_MARKERS = (
    "lawyer",
    "attorney",
    "injured",
    "injury",
    "fire",
    "smoke",
    "hospital",
    "lawsuit",
)
HIGH_MARKERS = (
    "wedding",
    "damaged",
    "crushed",
    "forever",
    "ridiculous",
    "today or",
    "need this before",
    "charged twice",
    "can't use the bike",
    "do something",
)


def _score_intent(text: str) -> tuple[Intent, int, list[str]]:
    lowered = text.lower()
    best_intent = Intent.OTHER
    best_score = 0
    hits: list[str] = []
    for intent, keywords in INTENT_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in lowered]
        score = len(matched)
        # Missing charger should not lose to a generic "return" mention.
        if intent == Intent.MISSING_PARTS and "charger" in lowered and "missing" in lowered:
            score += 2
        if intent == Intent.BILLING and "charged twice" in lowered:
            score += 2
        if intent == Intent.DAMAGED and "damaged" in lowered:
            score += 1
        if score > best_score:
            best_score = score
            best_intent = intent
            hits = matched
    return best_intent, best_score, hits


def _urgency(text: str, intent: Intent) -> tuple[Urgency, str]:
    lowered = text.lower()
    if any(marker in lowered for marker in CRITICAL_MARKERS):
        return Urgency.CRITICAL, "legal or safety language"
    if any(marker in lowered for marker in HIGH_MARKERS):
        return Urgency.HIGH, "time-sensitive or angry language"
    if intent in {Intent.DAMAGED, Intent.BILLING, Intent.WRONG_ITEM, Intent.MISSING_PARTS}:
        return Urgency.HIGH, "operational issue that blocks use or money"
    if intent in {Intent.PRODUCT_QUESTION}:
        return Urgency.LOW, "question only"
    if intent in {Intent.ORDER_STATUS} and not re.search(r"stuck|late|forever|weeks", lowered):
        return Urgency.MEDIUM, "status check"
    if intent in {Intent.REFUND, Intent.RETURN, Intent.CANCEL, Intent.WARRANTY, Intent.ORDER_STATUS}:
        return Urgency.MEDIUM, "standard request"
    return Urgency.MEDIUM, "default"


def classify_rules(ticket: Ticket) -> Classification:
    intent, score, hits = _score_intent(ticket.full_text)
    urgency, urgency_why = _urgency(ticket.full_text, intent)
    hit_text = ", ".join(repr(h) for h in hits[:4]) if hits else "no strong keyword"
    rationale = f"Intent from {hit_text}. Urgency: {urgency_why}."
    confidence = min(0.93, 0.45 + 0.12 * score)
    if intent == Intent.OTHER:
        confidence = 0.35
        rationale = "No strong intent match; treat as other and escalate if needed."
    return Classification(
        intent=intent,
        urgency=urgency,
        rationale=rationale,
        confidence=round(confidence, 2),
        engine="rules",
    )
