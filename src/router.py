import time
import requests
from typing import Any, Dict

from .health import HealthManager
from .provider import ProviderRegistry


class Router:
    def __init__(self, registry: ProviderRegistry, health_manager: HealthManager, scheduler):
        self.registry = registry
        self.health_manager = health_manager
        self.scheduler = scheduler

    def route_request(self, task_type: str, prompt: str, **kwargs) -> Dict[str, Any]:
        picked = self.scheduler.select(task_type)
        if not picked:
            return {"error": "no provider/model available"}

        provider_name = picked["provider"]
        model_id = picked["model"]

        start = time.time()
        try:
            # 这里做 Provider 通用调用适配。
            # 暂时只是模拟返回内容
            response = {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_id,
                "choices": [{"text": f"[Simulated] {prompt}", "index": 0, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            self.health_manager.record_result(provider_name, model_id, (time.time() - start) * 1000, True)
            return response
        except Exception as e:
            self.health_manager.record_result(provider_name, model_id, (time.time() - start) * 1000, False)
            return {"error": str(e)}
