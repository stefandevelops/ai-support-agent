"""Optional LLM path. Demo mode never imports a vendor SDK or needs a key."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import httpx

from support_copilot.models import (
    Classification,
    Draft,
    Intent,
    Order,
    PolicyChunk,
    Resolution,
    Ticket,
    Urgency,
)

CLASSIFY_SCHEMA = """Return JSON only:
{"intent": "<one of order_status,refund,return,damaged,missing_parts,wrong_item,warranty,cancel,billing,product_question,other>",
 "urgency": "<one of low,medium,high,critical>",
 "rationale": "<one sentence>",
 "confidence": <0-1 float>}"""


def llm_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))


def engine_label() -> str:
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return "demo (rules, no API key)"


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("LLM did not return JSON")
    return json.loads(match.group(0))


def _chat(system: str, user: str) -> str:
    if os.getenv("OPENAI_API_KEY"):
        return _openai_chat(system, user)
    if os.getenv("GEMINI_API_KEY"):
        return _gemini_chat(system, user)
    raise RuntimeError("No LLM key configured")


def _openai_chat(system: str, user: str) -> str:
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(f"{base}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def _gemini_chat(system: str, user: str) -> str:
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    key = os.getenv("GEMINI_API_KEY")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.2},
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def classify_llm(ticket: Ticket) -> Classification:
    user = f"Subject: {ticket.subject}\nFrom: {ticket.from_name} <{ticket.from_email}>\n\n{ticket.body}\n\n{CLASSIFY_SCHEMA}"
    raw = _extract_json(_chat("You classify ecommerce support emails. Be conservative with urgency.", user))
    return Classification(
        intent=Intent(raw["intent"]),
        urgency=Urgency(raw["urgency"]),
        rationale=str(raw.get("rationale", "LLM classification")),
        confidence=float(raw.get("confidence", 0.7)),
        engine="llm",
    )


def _order_blob(order: Optional[Order]) -> str:
    if not order:
        return "No order found."
    return (
        f"{order.id} | {order.customer_name} | {order.product} | ${order.amount:.2f} | "
        f"status={order.status} | ordered={order.ordered_at} | shipped={order.shipped_at} | "
        f"delivered={order.delivered_at} | tracking={order.tracking} {order.carrier} | "
        f"custom={order.is_custom} | in_stock={order.in_stock} | serial={order.serial}"
    )


def draft_llm(
    ticket: Ticket,
    classification: Classification,
    order: Optional[Order],
    resolution: Resolution,
    policies: list[PolicyChunk],
    fallback: Draft,
) -> Draft:
    policy_text = "\n".join(f"- {chunk.title}: {chunk.body}" for chunk in policies) or "None"
    system = (
        "You draft customer-support email replies for Ridgeway, an e-bike shop. "
        "A human will review every message. Never claim the email was sent. "
        "Do not invent refunds, replacements, or credits that contradict the resolution code. "
        "The resolution code is the source of truth. Sign as '— Priya, Ridgeway Support'. "
        "Return JSON: {\"reply\": \"...\", \"internal_note\": \"...\"}."
    )
    user = (
        f"Resolution code: {resolution.code.value}\n"
        f"Reason: {resolution.reason}\n"
        f"Intent: {classification.intent.value} | Urgency: {classification.urgency.value}\n"
        f"Order: {_order_blob(order)}\n"
        f"Policy:\n{policy_text}\n\n"
        f"Customer email:\nSubject: {ticket.subject}\n{ticket.body}\n"
    )
    try:
        raw = _extract_json(_chat(system, user))
        reply = str(raw["reply"]).strip()
        note = str(raw["internal_note"]).strip()
        if not reply:
            return fallback
        if "Nothing is sent" not in note:
            note = note + "\nNothing is sent until a human approves this draft."
        return Draft(reply=reply, internal_note=note, engine="llm")
    except (KeyError, ValueError, httpx.HTTPError, json.JSONDecodeError):
        return fallback
