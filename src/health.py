import time
from typing import Optional

from .provider import ProviderRegistry, ProviderState, ModelState


class HealthManager:
    def __init__(self, registry: ProviderRegistry, config: dict = None):
        self.registry = registry
        self.config = config or {}
        self.base_cool_down = self.config.get("cool_down_sec", 300)
        self.error_rate_threshold = self.config.get("error_rate", 0.2)
        self.p90_latency_threshold = self.config.get("p90_latency_ms", 1200)

    def record_result(self, provider_name: str, model_id: str, latency_ms: float, success: bool, error_msg: str = None):
        provider = self.registry.get_provider(provider_name)
        if not provider:
            return
        model = provider.models.get(model_id)
        if not model:
            return

        now = time.time()
        model.last_used_at = now
        model.latency_window.append(latency_ms)
        
        if success:
            model.success_count += 1
            # If a model succeeds, we might want to reset provider retry count if it was unhealthy
            if provider.status == "cooling_down":
                provider.status = "healthy"
                provider.retry_count = 0
        else:
            model.error_count += 1
            # Immediate exclusion for 429 (Quota Exhausted)
            if error_msg and "429" in error_msg:
                provider.status = "unstable"
                provider.last_check_at = now
                provider.retry_count += 1
                # Mark all models of this provider as potentially exhausted for immediate exclusion
                for m in provider.models.values():
                    m.last_latency_ms = 9999 # Penalty

    def evaluate(self):
        now = time.time()
        for provider in self.registry.all_providers():
            err_rate = provider.average_error_rate
            p99 = provider.p99_latency_ms

            # 1. Check if it should be marked as unstable
            if err_rate >= self.error_rate_threshold or p99 >= self.p90_latency_threshold:
                if provider.status != "unstable":
                    provider.status = "unstable"
                    provider.last_check_at = now
                    provider.retry_count += 1
                continue

            # 2. Handle cooling down / recovery
            if provider.status == "unstable":
                # Adaptive cooling: wait longer if it keeps failing
                cool_down_period = self.base_cool_down * (2 ** (provider.retry_count - 1))
                if now - provider.last_check_at >= cool_down_period:
                    provider.status = "cooling_down" # Try it again
                    provider.last_check_at = now
            elif provider.status == "cooling_down":
                # If it's in cooling_down but hasn't been used yet, stay there.
                # If it was used and succeeded, record_result would have set it to healthy.
                # If it was used and failed, evaluate will push it back to unstable.
                pass
            else:
                # Healthy
                provider.status = "healthy"
                provider.last_check_at = now

    def get_provider_status(self, provider_name: str) -> Optional[str]:
        provider = self.registry.get_provider(provider_name)
        if provider:
            return provider.status
        return None
