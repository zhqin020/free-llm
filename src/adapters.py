import requests
import json
from typing import Dict, Any, List

class BaseAdapter:
    def chat_completion(self, api_key: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Base method for chat completions. Should be overridden by specific provider adapters.
        """
        raise NotImplementedError

class OpenRouterAdapter(BaseAdapter):
    def chat_completion(self, api_key: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/freellm-res", # Required by OpenRouter for some models
            "X-Title": "FreeLLM Router",
        }
        
        # Filter out task_type and other router-specific kwargs
        api_kwargs = {k: v for k, v in kwargs.items() if k not in ["task_type", "timeout"]}
        
        payload = {
            "model": model_id,
            "messages": messages,
            **api_kwargs
        }
        
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=kwargs.get("timeout", 20)
        )
        response.raise_for_status()
        return response.json()

class GoogleStudioAdapter(BaseAdapter):
    def chat_completion(self, api_key: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        # Google AI Studio OpenAI-compatible endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key={api_key}"
        headers = {
            "Content-Type": "application/json",
        }
        
        api_kwargs = {k: v for k, v in kwargs.items() if k not in ["task_type", "timeout"]}
        
        payload = {
            "model": model_id,
            "messages": messages,
            **api_kwargs
        }
        
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=kwargs.get("timeout", 20)
        )
        response.raise_for_status()
        return response.json()

class AdapterRegistry:
    def __init__(self):
        self._adapters = {
            "openrouter": OpenRouterAdapter(),
            "google_ai_studio": GoogleStudioAdapter(),
            # Fallback for generic OpenAI-compatible providers
            "openai": OpenRouterAdapter(), 
        }

    def get_adapter(self, provider_type: str) -> BaseAdapter:
        return self._adapters.get(provider_type, self._adapters["openai"])

adapter_registry = AdapterRegistry()
