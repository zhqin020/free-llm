import time
from typing import Any, Dict

from .health import HealthManager
from .provider import ProviderRegistry
from .adapters import adapter_registry


class Router:
    def __init__(self, registry: ProviderRegistry, health_manager: HealthManager, scheduler):
        self.registry = registry
        self.health_manager = health_manager
        self.scheduler = scheduler

    def route_request(self, task_type: str, messages: list, **kwargs) -> Dict[str, Any]:
        max_retries = kwargs.get("max_retries", 3)
        
        last_error = "no provider/model available"
        for attempt in range(max_retries):
            picked = self.scheduler.select(task_type)
            if not picked:
                break

            provider_name = picked["provider"]
            model_id = picked["model"]
            provider = self.registry.get_provider(provider_name)
            
            adapter = adapter_registry.get_adapter(provider.type)
            
            start = time.time()
            try:
                response = adapter.chat_completion(
                    api_key=provider.api_key,
                    model_id=model_id,
                    messages=messages,
                    **kwargs
                )
                self.health_manager.record_result(provider_name, model_id, (time.time() - start) * 1000, True)
                return response
            except Exception as e:
                self.health_manager.record_result(provider_name, model_id, (time.time() - start) * 1000, False)
                last_error = str(e)
                # Scheduler will pick another healthy/cooling_down provider next time
                continue

        return {"error": f"Failed after {max_retries} attempts. Last error: {last_error}"}
