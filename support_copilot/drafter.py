from __future__ import annotations

from typing import Optional

from support_copilot.models import (
    Classification,
    Draft,
    Order,
    PolicyChunk,
    Resolution,
    ResolutionCode,
    Ticket,
)

SIGN_OFF = "— Priya, Ridgeway Support"


def _first_name(ticket: Ticket, order: Optional[Order]) -> str:
    source = order.customer_name if order else ticket.from_name
    parts = source.split()
    if not parts or parts[0].lower() in {"unknown", "somebody"}:
        return "there"
    return parts[0]


def _money(amount: float) -> str:
    return f"${amount:,.0f}" if amount == int(amount) else f"${amount:,.2f}"


def _order_line(order: Order) -> str:
    bits = [f"order {order.id}", order.product, _money(order.amount), f"status {order.status}"]
    if order.tracking:
        bits.append(f"tracking {order.tracking} ({order.carrier or 'carrier'})")
    if order.delivered_at:
        bits.append(f"delivered {order.delivered_at}")
    return " · ".join(bits)


def _policy_line(policies: list[PolicyChunk]) -> str:
    if not policies:
        return "No policy chunk matched."
    return "; ".join(f"{chunk.title}: {chunk.body}" for chunk in policies[:2])


def draft_internal_note(
    ticket: Ticket,
    classification: Classification,
    order: Optional[Order],
    resolution: Resolution,
    policies: list[PolicyChunk],
) -> str:
    del ticket
    order_bit = _order_line(order) if order else "No order matched."
    return (
        f"Intent: {classification.intent.value} ({classification.confidence:.0%}) | "
        f"Urgency: {classification.urgency.value}\n"
        f"{classification.rationale}\n"
        f"Order: {order_bit}\n"
        f"Resolution: {resolution.code.value}\n"
        f"Why: {resolution.reason}\n"
        f"Policy: {_policy_line(policies)}\n"
        "Nothing is sent until a human approves this draft."
    )


def _reply(ticket: Ticket, order: Optional[Order], resolution: Resolution) -> str:
    name = _first_name(ticket, order)
    text = ticket.full_text.lower()
    code = resolution.code

    if order is None:
        return (
            f"Hi {name},\n\n"
            "I looked in our orders and I don't have a match for this email yet. "
            "Could you reply with the order number from your confirmation? It looks like RW-#####.\n\n"
            "Once I have that I can check status, returns, or a refund without making you repeat the story.\n\n"
            f"{SIGN_OFF}"
        )

    product = order.product
    oid = order.id
    amount = _money(order.amount)

    if code == ResolutionCode.TRACKING_PROVIDED:
        tracking = (
            f"Tracking is {order.tracking} with {order.carrier}. "
            if order.tracking
            else "A tracking email goes out as soon as the carrier scans it. "
        )
        if order.status == "delivered":
            status = (
                f"It shows as delivered on {order.delivered_at}. "
                "If that's not what you have on the porch, say so and we'll open a carrier trace."
            )
        else:
            status = "Standard ground is 5–8 business days after it leaves us."
        return (
            f"Hi {name},\n\n"
            f"I pulled up {oid} — your {product} is marked {order.status}. {tracking}{status}\n\n"
            f"{SIGN_OFF}"
        )

    if code == ResolutionCode.INFO_PROVIDED:
        if order.status == "processing":
            body = (
                f"Your {product} ({oid}) is still in processing at the warehouse — it hasn't shipped, "
                "so there's no tracking number yet. Standard ground is 5–8 business days after it leaves us. "
                "I'll write again when the label prints."
            )
        elif "range" in text:
            body = (
                "For the City Step-Through in eco mode, most riders in the 140–180 lb range see about "
                "30–40 miles in a hilly city with mixed assist, less if you're on boost the whole commute. "
                "The 40-mile figure on the site is a lab-style loop, not a promise.\n\n"
                f"Your {oid} is on the way; this doesn't change the order."
            )
        else:
            body = f"Here's where {oid} stands: {order.status}. Tell me if you needed a different detail."
        return f"Hi {name},\n\n{body}\n\n{SIGN_OFF}"

    if code == ResolutionCode.RETURN_LABEL_ISSUED:
        return (
            f"Hi {name},\n\n"
            f"You're inside the 30-day window for {oid} ({product}, delivered {order.delivered_at}). "
            f"I'll send a prepaid return label to {order.email}. Please include the battery, charger, and keys.\n\n"
            f"We inspect at the warehouse, then refund {amount} to the original payment method — usually 5–7 "
            "business days after it lands. If you only rode it around the block we'll waive the restocking fee.\n\n"
            f"{SIGN_OFF}"
        )

    if code == ResolutionCode.REFUND_APPROVED:
        if order.status == "delivered":
            body = (
                f"We'll refund {amount} for {oid} to the original payment method, including original shipping. "
                "Please keep the bike until the return label arrives so the carrier can pick up the damaged or incorrect unit."
            )
        else:
            body = (
                f"{oid} hasn't shipped, so I'm cancelling it and refunding {amount} today. "
                "You don't need to return anything."
            )
        return f"Hi {name},\n\n{body}\n\n{SIGN_OFF}"

    if code == ResolutionCode.REFUND_DENIED:
        if order.is_custom:
            body = (
                f"{oid} is a custom build, and those are final sale — we can't take it back for a refund "
                "because of the paint and rack work. If something is actually wrong with the bike (defect or "
                "transit damage), reply with photos and I'll treat it as a warranty or damage claim instead."
            )
        else:
            body = (
                f"The 30-day return window for {oid} started on delivery ({order.delivered_at}), so we're past it. "
                "I can't issue a refund for a change of mind at this point. If the bike has a defect, we can still look at warranty."
            )
        return f"Hi {name},\n\n{body}\n\n{SIGN_OFF}"

    if code == ResolutionCode.REPLACEMENT_SHIPPED:
        if "charger" in text or "missing" in text:
            body = (
                f"Sorry — that's on us. For {oid} I'll ship the missing charger today; you don't need to send the bike back. "
                "Accessories sometimes leave in a second carton, but you shouldn't have to wait on that."
            )
        else:
            body = (
                f"Sorry the {product} arrived in that state. Transit damage and wrong-item shipments are on Ridgeway. "
                f"I'll send a replacement for {oid} and a prepaid label for the unit you have. Please don't ride it. "
                "Photos of the box, the damage, and the serial number help the carrier claim — attach them if you haven't."
            )
        return f"Hi {name},\n\n{body}\n\n{SIGN_OFF}"

    if code == ResolutionCode.WARRANTY_CLAIM_OPENED:
        serial = f", serial {order.serial}" if order.serial else ""
        return (
            f"Hi {name},\n\n"
            f"I opened a warranty claim on {oid} ({product}{serial}). "
            "Battery and electronics are covered for a year from delivery. "
            "Reply with a photo of the display/cycle count and the serial if you have it handy, "
            "and we'll go next step on a battery swap or inspection.\n\n"
            f"{SIGN_OFF}"
        )

    if code == ResolutionCode.WARRANTY_DENIED:
        if "pressure" in text or "wash" in text:
            extra = "Pressure washing and submersion aren't covered — water in the motor or controller is an exclusion. "
        else:
            extra = "This one is outside the coverage window. "
        return (
            f"Hi {name},\n\n"
            f"I looked at {oid}. {extra}"
            "We can still quote a repair through an authorized shop if you want that path. "
            "I won't pretend it's a warranty replacement.\n\n"
            f"{SIGN_OFF}"
        )

    if code == ResolutionCode.CANCELLATION_APPROVED:
        return (
            f"Hi {name},\n\n"
            f"{oid} hasn't shipped, so I've cancelled it. Refund of {amount} goes back to the original "
            "payment method today (card refunds can take 3–5 business days to show).\n\n"
            f"{SIGN_OFF}"
        )

    if code == ResolutionCode.CANCELLATION_DENIED:
        tracking = f" ({order.tracking} via {order.carrier})" if order.tracking else ""
        return (
            f"Hi {name},\n\n"
            f"{oid} already shipped{tracking}, so I can't cancel it in the warehouse. "
            "You can refuse the delivery, or return it after it arrives under the 30-day policy. "
            "Say which you prefer and I'll set it up.\n\n"
            f"{SIGN_OFF}"
        )

    if code == ResolutionCode.DELAY_CREDIT_OFFERED:
        return (
            f"Hi {name},\n\n"
            f"You're right that {oid} is outside the 5–8 business day window — tracking {order.tracking} "
            f"has been sitting with {order.carrier}. I can't refund shipping for a carrier delay, but I can "
            "put a $25 store credit on the account, and I've asked UPS for a trace. "
            "I'll write when they move it or confirm a loss.\n\n"
            f"{SIGN_OFF}"
        )

    return (
        f"Hi {name},\n\n"
        "I have your note and I'm passing it to a specialist rather than guessing from the draft queue. "
        "Someone on the team will follow up on this thread.\n\n"
        f"{SIGN_OFF}"
    )


def draft_rules(
    ticket: Ticket,
    classification: Classification,
    order: Optional[Order],
    resolution: Resolution,
    policies: list[PolicyChunk],
) -> Draft:
    return Draft(
        reply=_reply(ticket, order, resolution),
        internal_note=draft_internal_note(ticket, classification, order, resolution, policies),
        engine="rules",
    )
