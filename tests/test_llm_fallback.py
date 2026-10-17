import json

import httpx

from support_copilot.data_loader import load_tickets
from support_copilot.drafter import draft_rules
from support_copilot.llm import classify_llm, draft_llm
from support_copilot.models import Classification, Intent, Resolution, ResolutionCode, Urgency
from support_copilot.pipeline import run_copilot


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


def test_classify_llm_parses_openai_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    content = json.dumps(
        {
            "intent": "refund",
            "urgency": "medium",
            "rationale": "Customer asked for a refund.",
            "confidence": 0.88,
        }
    )
    payload = {"choices": [{"message": {"content": content}}]}

    def fake_post(self, url, json=None, headers=None):
        assert "chat/completions" in url
        assert headers["Authorization"] == "Bearer sk-test"
        return DummyResponse(payload)

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    ticket = next(t for t in load_tickets() if t.id == "T-1002")
    result = classify_llm(ticket)
    assert result.intent is Intent.REFUND
    assert result.engine == "llm"


def test_draft_llm_falls_back_on_bad_json(monkeypatch):
    ticket = next(t for t in load_tickets() if t.id == "T-1001")
    out = run_copilot(ticket, use_llm=False)
    fallback = draft_rules(
        ticket, out.classification, out.order, out.resolution, out.policies
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def fake_post(self, url, json=None, headers=None):
        return DummyResponse({"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    drafted = draft_llm(
        ticket,
        Classification(Intent.ORDER_STATUS, Urgency.MEDIUM, "x", 0.5, "llm"),
        out.order,
        Resolution(ResolutionCode.TRACKING_PROVIDED, "tracking"),
        out.policies,
        fallback,
    )
    assert drafted.engine == "rules"
    assert drafted.reply == fallback.reply


def test_pipeline_keeps_rules_when_llm_raises(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("support_copilot.pipeline.classify_llm", boom)
    ticket = next(t for t in load_tickets() if t.id == "T-1007")
    out = run_copilot(ticket, use_llm=True)
    assert out.resolution.code is ResolutionCode.CANCELLATION_APPROVED
    assert out.draft.engine == "rules"
