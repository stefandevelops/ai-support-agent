from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from support_copilot.clock import today
from support_copilot.models import Intent, Order, PolicyChunk, Resolution, ResolutionCode, Ticket, Urgency

RETURN_DAYS = 30
DELAY_CREDIT_AFTER = timedelta(days=14)  # ~10 business days, kept simple


def _days_since_delivery(order: Order, on: date) -> Optional[int]:
    delivered = order.delivered_date()
    if not delivered:
        return None
    return (on - delivered).days


def _in_return_window(order: Order, on: date) -> bool:
    elapsed = _days_since_delivery(order, on)
    return elapsed is not None and 0 <= elapsed <= RETURN_DAYS


def resolve(
    ticket: Ticket,
    intent: Intent,
    urgency: Urgency,
    order: Optional[Order],
    policies: list[PolicyChunk],
) -> Resolution:
    policy_ids = [chunk.id for chunk in policies]
    on = today()

    if urgency == Urgency.CRITICAL and intent not in {Intent.BILLING}:
        return Resolution(
            code=ResolutionCode.ESCALATE_TO_HUMAN,
            reason="Critical language (legal or safety). Do not auto-draft a commitment.",
            policy_ids=policy_ids,
        )

    if order is None:
        return Resolution(
            code=ResolutionCode.ESCALATE_TO_HUMAN,
            reason="No matching order in the database. Need the customer to confirm the order number.",
            policy_ids=policy_ids,
        )

    if intent == Intent.BILLING:
        return Resolution(
            code=ResolutionCode.ESCALATE_TO_HUMAN,
            reason="Billing disputes are reviewed by payments. Copilot should not reverse charges.",
            policy_ids=policy_ids,
        )

    if intent == Intent.PRODUCT_QUESTION:
        return Resolution(
            code=ResolutionCode.INFO_PROVIDED,
            reason="Product question. Share published guidance; no order change.",
            policy_ids=policy_ids,
        )

    if intent == Intent.ORDER_STATUS:
        if order.status == "shipped" and order.shipped_date() and on - order.shipped_date() >= DELAY_CREDIT_AFTER:
            return Resolution(
                code=ResolutionCode.DELAY_CREDIT_OFFERED,
                reason="In transit past the delay threshold. Offer $25 store credit and current tracking.",
                policy_ids=policy_ids,
            )
        if order.status in {"shipped", "delivered"} and order.tracking:
            return Resolution(
                code=ResolutionCode.TRACKING_PROVIDED,
                reason="Order is in the carrier network. Share tracking and status.",
                policy_ids=policy_ids,
            )
        return Resolution(
            code=ResolutionCode.INFO_PROVIDED,
            reason="Order has not shipped yet. Share processing status; no tracking.",
            policy_ids=policy_ids,
        )

    if intent == Intent.CANCEL:
        if order.status == "processing":
            return Resolution(
                code=ResolutionCode.CANCELLATION_APPROVED,
                reason="Not shipped. Cancel in full and refund to the original payment method.",
                policy_ids=policy_ids,
            )
        return Resolution(
            code=ResolutionCode.CANCELLATION_DENIED,
            reason="Already shipped. Cannot cancel in-flight; customer can refuse delivery or return after.",
            policy_ids=policy_ids,
        )

    if intent in {Intent.REFUND, Intent.RETURN}:
        if order.is_custom:
            return Resolution(
                code=ResolutionCode.REFUND_DENIED,
                reason="Custom build is final sale and not returnable.",
                policy_ids=policy_ids,
            )
        if order.status == "processing":
            return Resolution(
                code=ResolutionCode.REFUND_APPROVED,
                reason="Not shipped. Refund without a return.",
                policy_ids=policy_ids,
            )
        if order.status in {"shipped"}:
            return Resolution(
                code=ResolutionCode.CANCELLATION_DENIED,
                reason="Already shipped. Ask the customer to refuse delivery or return after arrival.",
                policy_ids=policy_ids,
            )
        if _in_return_window(order, on):
            return Resolution(
                code=ResolutionCode.RETURN_LABEL_ISSUED,
                reason="Delivered within the 30-day window. Prepaid label, inspect, then refund.",
                policy_ids=policy_ids,
            )
        return Resolution(
            code=ResolutionCode.REFUND_DENIED,
            reason="Outside the 30-day return window (from delivery date).",
            policy_ids=policy_ids,
        )

    if intent in {Intent.DAMAGED, Intent.WRONG_ITEM}:
        if order.in_stock:
            return Resolution(
                code=ResolutionCode.REPLACEMENT_SHIPPED,
                reason="Inbound damage or wrong item is on us. Replacement in stock; prepaid return of the original.",
                policy_ids=policy_ids,
            )
        return Resolution(
            code=ResolutionCode.REFUND_APPROVED,
            reason="Inbound damage or wrong item, replacement not in stock. Full refund including original shipping.",
            policy_ids=policy_ids,
        )

    if intent == Intent.MISSING_PARTS:
        return Resolution(
            code=ResolutionCode.REPLACEMENT_SHIPPED,
            reason="Missing part. Ship the part; do not require a full bike return.",
            policy_ids=policy_ids,
        )

    if intent == Intent.WARRANTY:
        text = ticket.full_text.lower()
        excluded = any(
            marker in text
            for marker in ("pressure wash", "pressure-washed", "crash", "submerged")
        )
        delivered = order.delivered_date()
        expired = delivered is not None and (on - delivered).days > 365
        if excluded or expired:
            return Resolution(
                code=ResolutionCode.WARRANTY_DENIED,
                reason="Outside coverage (exclusion or past the battery/electronics window).",
                policy_ids=policy_ids,
            )
        return Resolution(
            code=ResolutionCode.WARRANTY_CLAIM_OPENED,
            reason="In-warranty defect. Open a claim; ask for photos and serial if missing.",
            policy_ids=policy_ids,
        )

    return Resolution(
        code=ResolutionCode.ESCALATE_TO_HUMAN,
        reason="Intent is unclear. Leave it for a person.",
        policy_ids=policy_ids,
    )
