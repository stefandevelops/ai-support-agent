from __future__ import annotations

from support_copilot.classifier import classify_rules
from support_copilot.data_loader import load_orders, load_policies, load_tickets
from support_copilot.drafter import draft_rules
from support_copilot.entities import extract_entities
from support_copilot.llm import classify_llm, draft_llm, llm_configured
from support_copilot.models import CopilotOutput, Ticket
from support_copilot.orders import OrderStore
from support_copilot.policies import PolicyIndex
from support_copilot.resolver import resolve


def run_copilot(
    ticket: Ticket,
    order_store: OrderStore | None = None,
    policy_index: PolicyIndex | None = None,
    use_llm: bool | None = None,
) -> CopilotOutput:
    order_store = order_store or OrderStore(load_orders())
    policy_index = policy_index or PolicyIndex(load_policies())
    if use_llm is None:
        use_llm = llm_configured()

    entities = extract_entities(ticket)
    order = order_store.lookup(entities)

    classification = classify_rules(ticket)
    if use_llm:
        try:
            classification = classify_llm(ticket)
        except Exception:
            pass

    policies = policy_index.retrieve(classification.intent, ticket)
    resolution = resolve(ticket, classification.intent, classification.urgency, order, policies)
    draft = draft_rules(ticket, classification, order, resolution, policies)
    if use_llm:
        draft = draft_llm(ticket, classification, order, resolution, policies, fallback=draft)

    return CopilotOutput(
        ticket=ticket,
        entities=entities,
        classification=classification,
        order=order,
        policies=policies,
        resolution=resolution,
        draft=draft,
    )


def run_inbox() -> list[CopilotOutput]:
    orders = OrderStore(load_orders())
    policies = PolicyIndex(load_policies())
    return [run_copilot(ticket, order_store=orders, policy_index=policies) for ticket in load_tickets()]
