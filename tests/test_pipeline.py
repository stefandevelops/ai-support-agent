from support_copilot.data_loader import load_tickets
from support_copilot.models import Intent, ResolutionCode, Urgency
from support_copilot.pipeline import run_copilot, run_inbox
from support_copilot.store import ReviewStore

EXPECTED = {
    "T-1001": ResolutionCode.TRACKING_PROVIDED,
    "T-1002": ResolutionCode.RETURN_LABEL_ISSUED,
    "T-1003": ResolutionCode.REPLACEMENT_SHIPPED,
    "T-1004": ResolutionCode.REFUND_DENIED,
    "T-1005": ResolutionCode.REPLACEMENT_SHIPPED,
    "T-1006": ResolutionCode.WARRANTY_CLAIM_OPENED,
    "T-1007": ResolutionCode.CANCELLATION_APPROVED,
    "T-1008": ResolutionCode.CANCELLATION_DENIED,
    "T-1009": ResolutionCode.REFUND_DENIED,
    "T-1010": ResolutionCode.DELAY_CREDIT_OFFERED,
    "T-1011": ResolutionCode.RETURN_LABEL_ISSUED,
    "T-1012": ResolutionCode.WARRANTY_DENIED,
    "T-1013": ResolutionCode.INFO_PROVIDED,
    "T-1014": ResolutionCode.TRACKING_PROVIDED,
    "T-1015": ResolutionCode.REFUND_APPROVED,
    "T-1016": ResolutionCode.ESCALATE_TO_HUMAN,
    "T-1017": ResolutionCode.INFO_PROVIDED,
    "T-1018": ResolutionCode.ESCALATE_TO_HUMAN,
}


def test_sample_inbox_size():
    tickets = load_tickets()
    assert 15 <= len(tickets) <= 20


def test_resolutions_for_sample_inbox():
    by_id = {out.ticket.id: out for out in run_inbox()}
    assert set(by_id) == set(EXPECTED)
    for ticket_id, code in EXPECTED.items():
        assert by_id[ticket_id].resolution.code is code, ticket_id


def test_demo_mode_does_not_use_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ticket = next(t for t in load_tickets() if t.id == "T-1001")
    out = run_copilot(ticket, use_llm=False)
    assert out.classification.engine == "rules"
    assert out.draft.engine == "rules"
    assert "Priya" in out.draft.reply


def test_wismo_includes_tracking():
    ticket = next(t for t in load_tickets() if t.id == "T-1001")
    out = run_copilot(ticket, use_llm=False)
    assert out.classification.intent is Intent.ORDER_STATUS
    assert "1Z999AA10987654321" in out.draft.reply
    assert out.order is not None
    assert out.order.id == "RW-10510"


def test_damaged_is_high_urgency():
    ticket = next(t for t in load_tickets() if t.id == "T-1003")
    out = run_copilot(ticket, use_llm=False)
    assert out.classification.intent is Intent.DAMAGED
    assert out.classification.urgency is Urgency.HIGH


def test_unknown_order_escalates():
    ticket = next(t for t in load_tickets() if t.id == "T-1018")
    out = run_copilot(ticket, use_llm=False)
    assert out.order is None
    assert out.resolution.code is ResolutionCode.ESCALATE_TO_HUMAN
    assert out.classification.urgency is Urgency.CRITICAL


def test_store_approval_metrics():
    store = ReviewStore()
    first = store.pending()[0]
    store.approve(first.ticket.id, first.reply, first.internal_note)
    metrics = store.metrics()
    assert metrics.handled == 1
    assert metrics.approved == 1
    assert metrics.approval_rate == 1.0
    assert metrics.queued == len(store.cases) - 1


def test_store_edit_then_approve_and_reject():
    store = ReviewStore()
    pending = store.pending()
    a, b = pending[0], pending[1]
    store.approve(a.ticket.id, a.reply + "\n\nEdited by a human.", a.internal_note)
    store.reject(b.ticket.id, "Tone is off")
    metrics = store.metrics()
    assert metrics.approved_with_edits == 1
    assert metrics.rejected == 1
    assert metrics.handled == 2
    assert metrics.approval_rate == 0.5
