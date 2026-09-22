from datetime import datetime
from types import SimpleNamespace

import pytest

from app.ai import usage
from app.services.ai_usage_summary import build_ai_usage_summary


def test_extract_reported_tokens_from_openai_and_ollama_responses():
    assert usage.extract_token_counts(
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4)), "openai"
    ) == (12, 4)
    assert usage.extract_token_counts(
        {"usage": {"prompt_tokens": 0, "completion_tokens": 9}}, "openai"
    ) == (0, 9)
    assert usage.extract_token_counts({"prompt_eval_count": 7, "eval_count": 3}, "ollama") == (7, 3)


def test_missing_or_invalid_tokens_remain_unknown():
    assert usage.extract_token_counts({}, "ollama") == (None, None)
    assert usage.extract_token_counts(
        {"usage": {"prompt_tokens": True, "completion_tokens": -1}}, "openai"
    ) == (None, None)


def test_usage_scope_is_restored_after_nested_scope_and_error(monkeypatch):
    recorded = []
    monkeypatch.setattr(usage, "record_provider_usage", lambda **kwargs: recorded.append(usage._usage_context.get()))
    with usage.ai_usage_scope("tenant-a", "matching", "job-1"):
        usage.measured_provider_call("ollama", "model", lambda: {})
        with pytest.raises(ValueError):
            with usage.ai_usage_scope("tenant-b", "chat"):
                usage.measured_provider_call("ollama", "model", lambda: {})
                raise ValueError("test")
        usage.measured_provider_call("ollama", "model", lambda: {})
    assert [(item.tenant_slug, item.operation) for item in recorded] == [
        ("tenant-a", "matching"), ("tenant-b", "chat"), ("tenant-a", "matching")
    ]
    assert usage._usage_context.get() is None


def test_measured_call_preserves_response_and_exception(monkeypatch):
    captured = []
    monkeypatch.setattr(usage, "record_provider_usage", lambda **kwargs: captured.append(kwargs))
    response = {"eval_count": 3}
    assert usage.measured_provider_call("ollama", "model", lambda: response) is response
    assert captured[0]["duration_ms"] >= 0
    with pytest.raises(RuntimeError):
        usage.measured_provider_call("ollama", "model", lambda: (_ for _ in ()).throw(RuntimeError()))
    assert len(captured) == 2
    assert captured[1]["response"] is None
    assert captured[1]["failure_code"] == "provider_error"


def test_provider_failures_use_coarse_codes_only():
    assert usage.classify_provider_failure(TimeoutError("sensitive")) == "timeout"
    assert usage.classify_provider_failure(ConnectionError("sensitive")) == "dependency_unavailable"
    assert usage.classify_provider_failure(SimpleNamespaceError(429)) == "rate_limited"
    assert usage.classify_provider_failure(SimpleNamespaceError(503)) == "dependency_unavailable"
    assert usage.classify_provider_failure(SimpleNamespaceError(400)) == "provider_error"


class SimpleNamespaceError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


def test_user_scope_uses_tenant_and_preserves_existing_job_scope():
    user = SimpleNamespace(tenant=SimpleNamespace(slug="tenant-a"))

    @usage.track_user_ai_usage("crm_matching")
    def service(db, current_user):
        return usage._usage_context.get()

    direct = service(None, user)
    assert (direct.tenant_slug, direct.operation) == ("tenant-a", "crm_matching")
    assert usage._usage_context.get() is None
    with usage.ai_usage_scope("tenant-a", "crm_matching", "job-1"):
        nested = service(None, user)
        assert nested.correlation_id == "job-1"
    assert usage._usage_context.get() is None


def test_summary_aggregates_reported_usage_and_marks_missing_counts():
    rows = [
        SimpleNamespace(provider="ollama", model="m", operation="matching", calls=3, failed_calls=2,
                        input_tokens=20, output_tokens=10, calls_without_token_counts=1,
                        total_duration_ms=120),
        SimpleNamespace(provider="openai", model="n", operation="chat", calls=1, failed_calls=0,
                        input_tokens=None, output_tokens=None, calls_without_token_counts=1,
                        total_duration_ms=30),
    ]
    result = build_ai_usage_summary(rows, datetime(2026, 9, 1), datetime(2026, 10, 1))
    assert result["total_calls"] == 4
    assert result["total_failed_calls"] == 2
    assert result["input_tokens_reported"] == 20
    assert result["output_tokens_reported"] == 10
    assert result["calls_without_token_counts"] == 2
    assert result["groups"][0]["provider"] == "ollama"
    assert result["cost_available"] is False
