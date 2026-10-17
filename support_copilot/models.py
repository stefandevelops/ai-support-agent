from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional


class Intent(str, Enum):
    ORDER_STATUS = "order_status"
    REFUND = "refund"
    RETURN = "return"
    DAMAGED = "damaged"
    MISSING_PARTS = "missing_parts"
    WRONG_ITEM = "wrong_item"
    WARRANTY = "warranty"
    CANCEL = "cancel"
    BILLING = "billing"
    PRODUCT_QUESTION = "product_question"
    OTHER = "other"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionCode(str, Enum):
    TRACKING_PROVIDED = "TRACKING_PROVIDED"
    INFO_PROVIDED = "INFO_PROVIDED"
    RETURN_LABEL_ISSUED = "RETURN_LABEL_ISSUED"
    REFUND_APPROVED = "REFUND_APPROVED"
    REFUND_DENIED = "REFUND_DENIED"
    REPLACEMENT_SHIPPED = "REPLACEMENT_SHIPPED"
    WARRANTY_CLAIM_OPENED = "WARRANTY_CLAIM_OPENED"
    WARRANTY_DENIED = "WARRANTY_DENIED"
    CANCELLATION_APPROVED = "CANCELLATION_APPROVED"
    CANCELLATION_DENIED = "CANCELLATION_DENIED"
    DELAY_CREDIT_OFFERED = "DELAY_CREDIT_OFFERED"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"


class TicketStatus(str, Enum):
    PENDING = "pending_review"
    APPROVED = "approved"
    APPROVED_WITH_EDITS = "approved_with_edits"
    REJECTED = "rejected"


INTENT_LABELS = {
    Intent.ORDER_STATUS: "Where is my order",
    Intent.REFUND: "Refund",
    Intent.RETURN: "Return",
    Intent.DAMAGED: "Damaged in transit",
    Intent.MISSING_PARTS: "Missing parts",
    Intent.WRONG_ITEM: "Wrong item",
    Intent.WARRANTY: "Warranty",
    Intent.CANCEL: "Cancellation",
    Intent.BILLING: "Billing",
    Intent.PRODUCT_QUESTION: "Product question",
    Intent.OTHER: "Other",
}


@dataclass
class Ticket:
    id: str
    received_at: str
    from_name: str
    from_email: str
    subject: str
    body: str

    @property
    def full_text(self) -> str:
        return f"{self.subject}\n{self.body}"


@dataclass
class Order:
    id: str
    customer_name: str
    email: str
    product: str
    sku: str
    amount: float
    status: str
    ordered_at: str
    shipped_at: Optional[str]
    delivered_at: Optional[str]
    tracking: Optional[str]
    carrier: Optional[str]
    is_custom: bool
    in_stock: bool
    serial: Optional[str]
    notes: str = ""

    def delivered_date(self) -> Optional[date]:
        if not self.delivered_at:
            return None
        return date.fromisoformat(self.delivered_at)

    def ordered_date(self) -> date:
        return date.fromisoformat(self.ordered_at)

    def shipped_date(self) -> Optional[date]:
        if not self.shipped_at:
            return None
        return date.fromisoformat(self.shipped_at)


@dataclass
class PolicyChunk:
    id: str
    topic: str
    title: str
    body: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class Entities:
    order_id: Optional[str] = None
    email: Optional[str] = None
    serial: Optional[str] = None


@dataclass
class Classification:
    intent: Intent
    urgency: Urgency
    rationale: str
    confidence: float
    engine: str = "rules"


@dataclass
class Resolution:
    code: ResolutionCode
    reason: str
    policy_ids: list[str] = field(default_factory=list)


@dataclass
class Draft:
    reply: str
    internal_note: str
    engine: str = "rules"


@dataclass
class CopilotOutput:
    ticket: Ticket
    entities: Entities
    classification: Classification
    order: Optional[Order]
    policies: list[PolicyChunk]
    resolution: Resolution
    draft: Draft

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket.id,
            "intent": self.classification.intent.value,
            "urgency": self.classification.urgency.value,
            "resolution": self.resolution.code.value,
            "order_id": self.order.id if self.order else None,
            "engine": self.draft.engine,
        }


@dataclass
class ReviewCase:
    output: CopilotOutput
    status: TicketStatus = TicketStatus.PENDING
    reply: str = ""
    internal_note: str = ""
    rejection_reason: str = ""
    decided_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.reply:
            self.reply = self.output.draft.reply
        if not self.internal_note:
            self.internal_note = self.output.draft.internal_note

    @property
    def ticket(self) -> Ticket:
        return self.output.ticket

    def was_edited(self) -> bool:
        return (
            self.reply.strip() != self.output.draft.reply.strip()
            or self.internal_note.strip() != self.output.draft.internal_note.strip()
        )


def order_from_dict(raw: dict[str, Any]) -> Order:
    return Order(**raw)


def ticket_from_dict(raw: dict[str, Any]) -> Ticket:
    return Ticket(**raw)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_public_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return dict(obj)
