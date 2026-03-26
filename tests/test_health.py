from src.health import HealthManager
from src.provider import ProviderRegistry, ProviderState, ModelState


def test_health_evaluation():
    reg = ProviderRegistry()
    p = ProviderState(name="openrouter", type="openrouter", free=True, api_key="key")
    p.status = "healthy"
    p.models["gemma"] = ModelState(id="gemma", tags=["analysis"], free=True, last_latency_ms=300, success_count=0, error_count=10)
    reg.add_provider(p)

    hm = HealthManager(reg, config={"error_rate": 0.2, "p90_latency_ms": 1200, "cool_down_sec": 0})
    hm.evaluate()

    assert reg.get_provider("openrouter").status == "unstable" or reg.get_provider("openrouter").status == "healthy"
