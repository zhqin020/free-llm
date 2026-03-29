import requests
import json
import time
from typing import Dict, Any, List

class BaseAdapter:
    def _sanitize_key(self, key: str) -> str:
        if not key or len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Base method for chat completions.
        """
        raise NotImplementedError

    def _handle_response(self, response: requests.Response, url: str) -> Dict[str, Any]:
        if not response.ok:
            msg = response.text
            try:
                err_data = response.json()
                if isinstance(err_data, dict):
                    # For 429, we keep the full JSON for HealthManager to inspect structured details
                    if response.status_code == 429:
                        msg = response.text
                    # OpenAI / OpenRouter style
                    elif "error" in err_data:
                        if isinstance(err_data["error"], dict):
                            msg = err_data["error"].get("message", msg)
                        else:
                            msg = str(err_data["error"])
                    # Another common style (Google / Generic FastAPI)
                    elif "detail" in err_data:
                        msg = str(err_data["detail"])
            except:
                pass # Fallback to response.text
            
            print(f"DEBUG: Adapter Error Response ({response.status_code}): {msg[:500]}")
            raise Exception(f"{response.status_code} Client Error: {msg} for url: {url}")
            
        try:
            return response.json()
        except Exception as e:
            print(f"DEBUG: Failed to parse JSON from {url}. Raw: {response.text[:200]}")
            raise Exception(f"Failed to parse JSON response from {url}: {response.text[:100]}...")

class GenericOpenAIAdapter(BaseAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "FreeLLM-Router/1.0"
        }
        
        excluded_keys = ["task_type", "timeout", "max_retries", "model"]
        api_kwargs = {k: v for k, v in kwargs.items() if k not in excluded_keys}
        
        payload = {
            "model": model_id.strip(),
            "messages": messages,
            "stream": False,
            **api_kwargs
        }
        
        full_url = url if "/chat/completions" in url else f"{url.rstrip('/')}/chat/completions"
        print(f"DEBUG: Sending OpenAI request to {full_url}")
        print(f"DEBUG: Headers: {{'Authorization': 'Bearer {self._sanitize_key(api_key)}', 'Content-Type': 'application/json'}}")
        
        response = requests.post(
            full_url, 
            headers=headers, 
            json=payload, 
            timeout=kwargs.get("timeout", 20)
        )
        return self._handle_response(response, url)

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
        
        print(f"DEBUG: Sending OpenRouter request to {target_url}")
        print(f"DEBUG: Headers: {{'Authorization': 'Bearer {self._sanitize_key(api_key)}', ...}}")
        
        response = requests.post(
            target_url, 
            headers=headers, 
            json=payload, 
            timeout=kwargs.get("timeout", 20)
        )
        return self._handle_response(response, target_url)
    
class MistralAdapter(GenericOpenAIAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        # Alias 'codestral' to 'codestral-latest' for the standard endpoint 
        # because standard keys often only authorize the -latest version on the main API.
        target_model = model_id
        if "api.mistral.ai" in url and model_id == "codestral":
            print(f"DEBUG: Aliasing 'codestral' -> 'codestral-latest' for standard Mistral endpoint.")
            target_model = "codestral-latest"
            
        return super().chat_completion(api_key, url, target_model, messages, **kwargs)

class OpenCodeZenAdapter(GenericOpenAIAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        # Alias 'big-pickle-stealth' to 'big-pickle' because OpenCode Zen dropped '-stealth' from the ID.
        target_model = model_id
        if model_id == "big-pickle-stealth":
            print(f"DEBUG: Aliasing 'big-pickle-stealth' -> 'big-pickle' for OpenCode Zen.")
            target_model = "big-pickle"
            
        return super().chat_completion(api_key, url, target_model, messages, **kwargs)

class GoogleNativeAdapter(BaseAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        target_url = url
        # Gemini Native URL: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}
        # Sanitize model_id for URL path
        # Google expects lowercase, alphanumeric, hyphens, and periods
        clean_model = model_id.lower().replace(" ", "-")
        clean_model = "".join(c for c in clean_model if c.isalnum() or c in ("-", "."))
        
        # If user only provided base URL, construct it
        if "generativelanguage" in target_url and ":generateContent" not in target_url:
            if "/models/" not in target_url:
                # Base URL like https://generativelanguage.googleapis.com/v1beta
                target_url = target_url.rstrip("/") + f"/models/{clean_model}:generateContent"
            else:
                # URL has models but no action, e.g. .../models/gemini-1.5-flash
                target_url = target_url.rstrip("/") + ":generateContent"

        if "key=" not in target_url:
            sep = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{sep}key={api_key}"
            
        # Convert OpenAI messages to Gemini contents
        contents = []
        for m in messages:
            role = "user" if m["role"] != "assistant" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
            
        payload = {"contents": contents}
        
        # Sanitize target URL for logging (hide key)
        log_url = target_url.split("key=")[0]
        print(f"DEBUG: Sending Google Native request to {log_url}")
        
        response = requests.post(
            target_url, 
            headers={"Content-Type": "application/json"}, 
            json=payload, 
            timeout=kwargs.get("timeout", 30)
        )
        
        raw_res = self._handle_response(response, target_url)
        
        # Normalize Gemini native response TO OpenAI format
        try:
            text = raw_res["candidates"][0]["content"]["parts"][0]["text"]
            return {
                "id": f"gen-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_id,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            }
        except Exception as e:
            raw_str = json.dumps(raw_res)
            raise Exception(f"Failed to normalize Google Native response: {str(e)}. Raw: {raw_str[:200]}...")

class NvidiaAdapter(GenericOpenAIAdapter):
    def chat_completion(self, api_key: str, url: str, model_id: str, messages: list, **kwargs) -> dict:
        # Currently NVIDIA NIM is strictly OpenAI-compatible
        # but we use a specialized class for better diagnostics
        print(f"DEBUG: NVIDIA NIM Request Model: {model_id}")
        return super().chat_completion(api_key, url, model_id, messages, **kwargs)

class AdapterRegistry:
    def __init__(self):
        generic = GenericOpenAIAdapter()
        self._adapters = {
            "openrouter": OpenRouterAdapter(),
            "google_ai_studio": generic, # OpenAI-compatible layer
            "google_native": GoogleNativeAdapter(), # Native Gemini API
            "openai": generic,
            "deepseek": generic,
            "groq": generic,
            "mistral": MistralAdapter(),
            "mistral_codestral": MistralAdapter(),
            "opencode_zen": OpenCodeZenAdapter(),
            "nvidia": NvidiaAdapter(),
            "siliconflow": generic,
        }

    def get_adapter(self, provider_type: str) -> BaseAdapter:
        return self._adapters.get(provider_type, self._adapters["openai"])

adapter_registry = AdapterRegistry()
