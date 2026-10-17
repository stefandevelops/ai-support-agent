from __future__ import annotations

from support_copilot.models import Intent, PolicyChunk, Ticket

INTENT_TOPICS = {
    Intent.ORDER_STATUS: ("shipping",),
    Intent.REFUND: ("returns",),
    Intent.RETURN: ("returns",),
    Intent.DAMAGED: ("shipping", "returns"),
    Intent.MISSING_PARTS: ("shipping", "returns"),
    Intent.WRONG_ITEM: ("returns", "shipping"),
    Intent.WARRANTY: ("warranty",),
    Intent.CANCEL: ("returns",),
    Intent.BILLING: ("billing",),
    Intent.PRODUCT_QUESTION: ("shipping", "warranty"),
    Intent.OTHER: ("returns", "shipping", "warranty"),
}


class PolicyIndex:
    def __init__(self, chunks: list[PolicyChunk]):
        self.chunks = chunks

    def retrieve(self, intent: Intent, ticket: Ticket, limit: int = 3) -> list[PolicyChunk]:
        topics = set(INTENT_TOPICS.get(intent, ("returns", "shipping", "warranty")))
        text = ticket.full_text.lower()
        scored: list[tuple[int, PolicyChunk]] = []
        for chunk in self.chunks:
            score = 0
            if chunk.topic in topics:
                score += 5
            for keyword in chunk.keywords:
                if keyword.lower() in text:
                    score += 2
            title_hits = sum(1 for word in chunk.title.lower().split() if word in text)
            score += title_hits
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        picked = [chunk for _, chunk in scored[:limit]]
        if picked:
            return picked
        return [chunk for chunk in self.chunks if chunk.topic in topics][:limit]
