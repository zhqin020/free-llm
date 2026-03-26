import pytest

from src.provider import ProviderRegistry, ProviderState, ModelState
from src.scheduler import Scheduler


@pytest.fixture
def registry():
    reg = ProviderRegistry()
    p = ProviderState(name="openrouter", type="openrouter", free=True, api_key="key")
    p.status = "healthy"
    p.models["gemma"] = ModelState(id="gemma", tags=["analysis", "text"], free=True, last_latency_ms=220, success_count=5, error_count=0)
    reg.add_provider(p)

    q = ProviderState(name="google", type="google_ai_studio", free=False, api_key="key")
    q.status = "healthy"
    q.models["gemini"] = ModelState(id="gemini", tags=["analysis"], free=False, last_latency_ms=400, success_count=8, error_count=2)
    reg.add_provider(q)
    return reg


def test_select_best_model(registry):
    scheduler = Scheduler(registry, {"analysis": type("x", (), {"candidate_tags": ["analysis"]})()}, {})
    r = scheduler.select("analysis")
    assert r is not None
    assert r["provider"] == "openrouter"


def test_no_candidate_for_other_task(registry):
    scheduler = Scheduler(registry, {"trading": type("x", (), {"candidate_tags": ["trading"]})()}, {})
    r = scheduler.select("trading")
    assert r is None
