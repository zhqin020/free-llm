import time
from typing import Optional

from .provider import ProviderRegistry, ProviderState, ModelState


class HealthManager:
    def __init__(self, registry: ProviderRegistry, config: dict = None):
        self.registry = registry
        self.config = config or {}
        self.cool_down_sec = self.config.get("cool_down_sec", 300)

    def record_result(self, provider_name: str, model_id: str, latency_ms: float, success: bool):
        provider = self.registry.get_provider(provider_name)
        if not provider:
            return
        model = provider.models.get(model_id)
        if not model:
            return

        model.last_latency_ms = latency_ms
        if success:
            model.success_count += 1
        else:
            model.error_count += 1

    def evaluate(self):
        now = time.time()
        for provider in self.registry.all_providers():
            err_rate = provider.average_error_rate
            p99 = provider.p99_latency_ms

            if err_rate >= self.config.get("error_rate", 0.2) or p99 >= self.config.get("p90_latency_ms", 1200):
                provider.status = "unstable"
                provider.last_check_ms = now
            elif provider.status == "unstable" and provider.last_check_ms and now - provider.last_check_ms >= self.cool_down_sec:
                provider.status = "healthy"
                provider.last_check_ms = now
            else:
                provider.status = "healthy"
                provider.last_check_ms = now

    def get_provider_status(self, provider_name: str) -> Optional[str]:
        provider = self.registry.get_provider(provider_name)
        if provider:
            return provider.status
        return None
