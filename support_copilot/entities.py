from __future__ import annotations

import re

from support_copilot.models import Entities, Ticket

ORDER_RE = re.compile(r"\bRW[-\s]?(\d{4,6})\b", re.IGNORECASE)
SERIAL_RE = re.compile(r"\bRW-[A-Z]-\d{6}\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def extract_entities(ticket: Ticket) -> Entities:
    text = f"{ticket.from_email}\n{ticket.full_text}"
    order_match = ORDER_RE.search(text)
    serial_match = SERIAL_RE.search(text)
    order_id = f"RW-{order_match.group(1)}" if order_match else None
    return Entities(
        order_id=order_id,
        email=ticket.from_email.lower(),
        serial=serial_match.group(0).upper() if serial_match else None,
    )
