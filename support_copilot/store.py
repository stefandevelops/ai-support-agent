from __future__ import annotations

from dataclasses import dataclass

from support_copilot.models import ReviewCase, Ticket, TicketStatus, iso_now
from support_copilot.pipeline import run_copilot, run_inbox


@dataclass
class Metrics:
    queued: int
    handled: int
    approved: int
    approved_with_edits: int
    rejected: int
    approval_rate: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "queued": self.queued,
            "handled": self.handled,
            "approved": self.approved,
            "approved_with_edits": self.approved_with_edits,
            "rejected": self.rejected,
            "approval_rate": self.approval_rate,
        }


class ReviewStore:
    def __init__(self, cases: list[ReviewCase] | None = None):
        seeded = cases if cases is not None else [ReviewCase(output=out) for out in run_inbox()]
        self.cases: dict[str, ReviewCase] = {case.ticket.id: case for case in seeded}

    def pending(self) -> list[ReviewCase]:
        return [case for case in self.cases.values() if case.status == TicketStatus.PENDING]

    def decided(self) -> list[ReviewCase]:
        return [case for case in self.cases.values() if case.status != TicketStatus.PENDING]

    def get(self, ticket_id: str) -> ReviewCase:
        return self.cases[ticket_id]

    def add_ticket(self, ticket: Ticket) -> ReviewCase:
        case = ReviewCase(output=run_copilot(ticket))
        self.cases[ticket.id] = case
        return case

    def save_edits(self, ticket_id: str, reply: str, internal_note: str) -> ReviewCase:
        case = self.cases[ticket_id]
        case.reply = reply
        case.internal_note = internal_note
        return case

    def approve(self, ticket_id: str, reply: str, internal_note: str) -> ReviewCase:
        case = self.save_edits(ticket_id, reply, internal_note)
        case.status = (
            TicketStatus.APPROVED_WITH_EDITS if case.was_edited() else TicketStatus.APPROVED
        )
        case.decided_at = iso_now()
        return case

    def reject(self, ticket_id: str, reason: str = "") -> ReviewCase:
        case = self.cases[ticket_id]
        case.status = TicketStatus.REJECTED
        case.rejection_reason = reason
        case.decided_at = iso_now()
        return case

    def metrics(self) -> Metrics:
        approved = sum(1 for case in self.cases.values() if case.status == TicketStatus.APPROVED)
        edited = sum(
            1 for case in self.cases.values() if case.status == TicketStatus.APPROVED_WITH_EDITS
        )
        rejected = sum(1 for case in self.cases.values() if case.status == TicketStatus.REJECTED)
        handled = approved + edited + rejected
        rate = (approved + edited) / handled if handled else 0.0
        return Metrics(
            queued=len(self.pending()),
            handled=handled,
            approved=approved,
            approved_with_edits=edited,
            rejected=rejected,
            approval_rate=rate,
        )
