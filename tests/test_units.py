from support_copilot.classifier import classify_rules
from support_copilot.data_loader import load_orders, load_policies, load_tickets
from support_copilot.entities import extract_entities
from support_copilot.llm import engine_label, llm_configured
from support_copilot.models import Intent, ResolutionCode, Ticket, Urgency
from support_copilot.orders import OrderStore
from support_copilot.policies import PolicyIndex
from support_copilot.resolver import resolve


def test_extract_order_id_formats():
    ticket = Ticket(
        id="x",
        received_at="",
        from_name="A",
        from_email="a@example.com",
        subject="RW 10510",
        body="Please look at rw-10510",
    )
    entities = extract_entities(ticket)
    assert entities.order_id == "RW-10510"
    assert entities.email == "a@example.com"


def test_order_lookup_by_id_and_email():
    store = OrderStore(load_orders())
    ticket = next(t for t in load_tickets() if t.id == "T-1002")
    order = store.lookup(extract_entities(ticket))
    assert order is not None
    assert order.id == "RW-10482"
    assert order.email == "maya.chen@example.com"


def test_policy_retrieval_for_returns():
    index = PolicyIndex(load_policies())
    ticket = next(t for t in load_tickets() if t.id == "T-1002")
    chunks = index.retrieve(Intent.REFUND, ticket)
    assert chunks
    assert any(chunk.topic == "returns" for chunk in chunks)


def test_custom_build_denied():
    store = OrderStore(load_orders())
    ticket = next(t for t in load_tickets() if t.id == "T-1009")
    order = store.lookup(extract_entities(ticket))
    resolution = resolve(ticket, Intent.RETURN, Urgency.MEDIUM, order, [])
    assert resolution.code is ResolutionCode.REFUND_DENIED
    assert "custom" in resolution.reason.lower() or "final" in resolution.reason.lower()


def test_classifier_billing_and_product_question():
    billing = next(t for t in load_tickets() if t.id == "T-1016")
    question = next(t for t in load_tickets() if t.id == "T-1017")
    assert classify_rules(billing).intent is Intent.BILLING
    assert classify_rules(question).intent is Intent.PRODUCT_QUESTION
    assert classify_rules(question).urgency is Urgency.LOW


def test_demo_engine_label_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_configured() is False
    assert "demo" in engine_label()
