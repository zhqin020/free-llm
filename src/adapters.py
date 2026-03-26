import requests
import json
from typing import Dict, Any, List

class BaseAdapter:
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Base method for chat completions.
        """
        raise NotImplementedError

class GenericOpenAIAdapter(BaseAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        excluded_keys = ["task_type", "timeout", "max_retries", "model"]
        api_kwargs = {k: v for k, v in kwargs.items() if k not in excluded_keys}
        
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
        
        if not response.ok:
            try:
                err_data = response.json()
                msg = err_data.get("error", {}).get("message", response.text)
            except:
                msg = response.text
            raise Exception(f"{response.status_code} Client Error: {msg} for url: {url}")
            
        try:
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to parse JSON response from {url}: {response.text[:100]}...")

class OpenRouterAdapter(GenericOpenAIAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        # OpenRouter always uses its specific endpoint regardless of database URL
        target_url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/freellm-res", 
            "X-Title": "FreeLLM Router",
        }
        
        excluded_keys = ["task_type", "timeout", "max_retries", "model"]
        api_kwargs = {k: v for k, v in kwargs.items() if k not in excluded_keys}
        
        payload = {
            "model": model_id,
            "messages": messages,
            **api_kwargs
        }
        
        response = requests.post(
            target_url, 
            headers=headers, 
            json=payload, 
            timeout=kwargs.get("timeout", 20)
        )
        response.raise_for_status()
        return response.json()

class GoogleStudioAdapter(BaseAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        # Use the URL from database, but ensure it has the API key
        target_url = url
        if "key=" not in target_url:
            sep = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{sep}key={api_key}"
            
        headers = {
            "Content-Type": "application/json",
        }
        
        excluded_keys = ["task_type", "timeout", "max_retries", "model"]
        api_kwargs = {k: v for k, v in kwargs.items() if k not in excluded_keys}
        
        payload = {
            "model": model_id,
            "messages": messages,
            **api_kwargs
        }
        
        response = requests.post(
            target_url, 
            headers=headers, 
            json=payload, 
            timeout=kwargs.get("timeout", 20)
        )
        response.raise_for_status()
        return response.json()

class AdapterRegistry:
    def __init__(self):
        generic = GenericOpenAIAdapter()
        self._adapters = {
            "openrouter": OpenRouterAdapter(),
            "google_ai_studio": GoogleStudioAdapter(),
            "openai": generic,
            "deepseek": generic,
            "groq": generic,
            "mistral": generic,
            "nvidia": generic,
            "siliconflow": generic,
        }

    def get_adapter(self, provider_type: str) -> BaseAdapter:
        return self._adapters.get(provider_type, self._adapters["openai"])

adapter_registry = AdapterRegistry()
