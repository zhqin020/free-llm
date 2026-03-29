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
        override_model = kwargs.get("model")
        
        for attempt in range(max_retries):
            provider_name = None
            model_id = None
            
            if override_model and attempt == 0:
                # Try the requested model first
                found = False
                for p in self.registry.all_providers():
                    if override_model in p.models:
                        provider_name = p.name
                        model_id = override_model
                        found = True
                        break
                if not found:
                    print(f"WARNING: Requested model '{override_model}' not found in registry. Using scheduler.")
            
            if not provider_name:
                picked = self.scheduler.select(task_type)
                if not picked:
                    break
                provider_name = picked["provider"]
                model_id = picked["model"]
            provider = self.registry.get_provider(provider_name)
            if not provider or not provider.api_url:
                # Skip providers with no API endpoint configured
                last_error = f"provider {provider_name} has no API URL configured"
                continue
            
            adapter = adapter_registry.get_adapter(provider.type)
            
            start = time.time()
            try:
                print(f"INFO: Attempt {attempt + 1}: Routing to '{provider_name}' (Model: {model_id})")
                response = adapter.chat_completion(
                    api_key=provider.api_key,
                    url=provider.api_url,
                    model_id=model_id,
                    messages=messages,
                    **kwargs
                )
                self.health_manager.record_result(provider_name, model_id, (time.time() - start) * 1000, True)
                print(f"INFO: Successfully completed request via '{provider_name}'")
                return response
            except Exception as e:
                print(f"WARNING: Attempt {attempt + 1} failed via '{provider_name}': {str(e)}")
                self.health_manager.record_result(provider_name, model_id, (time.time() - start) * 1000, False, error_msg=str(e))
                last_error = str(e)
                # Scheduler will pick another healthy/cooling_down provider next time
                continue

        return {"error": f"Failed after {max_retries} attempts. Last error: {last_error}"}
