import time
import re
import json
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
            print(f"DEBUG: Provider '{provider_name}' NOT FOUND in registry. (Searched for: {provider_name})")
            return
        
        model = provider.models.get(model_id)
        if not model:
            print(f"DEBUG: Model '{model_id}' NOT FOUND for provider '{provider_name}'.")
            # We still want to handle 429 even without a model match!
            if not (error_msg and "429" in error_msg):
                return

        now = time.time()
        model.last_used_at = now
        model.latency_window.append(latency_ms)
        
        if success:
            model.success_count += 1
            model.cool_down_until = None # Clear on success
            # If a model succeeds, we might want to reset provider retry count if it was unhealthy
            if provider.status == "cooling_down":
                provider.status = "healthy"
                provider.retry_count = 0
        else:
            model.error_count += 1
            
            # 0. Check for model-specific "Not Found" or "Function Not Found" (Account Restrictions)
            # This is common for NVIDIA NIM (e.g. "Function '...' not found for account '...'")
            if error_msg and ("Function" in error_msg and "Not found" in error_msg):
                model.cool_down_until = now + 3600
                print(f"DEBUG: Restricted model detection: Cooling down '{model_id}' on '{provider_name}' for 1h.")
            elif error_msg and ("Model not found" in error_msg or "The model does not exist" in error_msg):
                model.cool_down_until = now + 3600 # 1h
                print(f"DEBUG: Model not found detection: Cooling down '{model_id}' on '{provider_name}' for 1h.")
            # Immediate exclusion for 429 (Quota Exhausted)
            if error_msg and ("429" in error_msg or "402" in error_msg):
                print(f"DEBUG: 429 detected for '{provider_name}'. Processing error message...")
                provider.status = "unstable"
                provider.last_check_at = now
                provider.retry_count += 1
                
                # 1. String-based prioritiezed detection for daily exhaustion
                if any(x in error_msg for x in ["PerDay", "Daily", "Quota exceeded", "GenerateRequestsPerDay", "402"]):
                    provider.cool_down_until = now + 3600
                    if provider.max_quota_day > 0:
                        provider.current_quota_day = provider.max_quota_day
                    print(f"DEBUG: Daily quota exhausted for '{provider_name}'. 1h lockout.")

                # 2. Try JSON parsing for structured Google/OpenRouter errors (with robustness)
                try:
                    # Look for JSON-like structure within the error message
                    json_match = re.search(r'\[(\{.*\})\]', error_msg, re.DOTALL) or re.search(r'(\{.*\})', error_msg, re.DOTALL)
                    if json_match:
                        # Clean up literal newlines within the JSON string for robustness
                        json_str = json_match.group(1)
                        data = json.loads(json_str, strict=False) 
                        err_obj = data.get("error", {})
                        
                        # Check for specifically 'PerDay' failures in details
                        details = err_obj.get("details", [])
                        for d in details:
                            if d.get("@type") == "type.googleapis.com/google.rpc.QuotaFailure":
                                for v in d.get("violations", []):
                                    if "PerDay" in v.get("quotaId", ""):
                                        provider.cool_down_until = now + 3600
                                        print(f"CRITICAL: QuotaFailure (PerDay) for '{provider_name}'.")
                except:
                    pass

                # 3. Fallback to regex for retryDelay (only if not already longer)
                match = re.search(r"(?:retry in|retry after|retryIn)\s*(\d+\.?\d*)s?", error_msg, re.IGNORECASE)
                if match:
                    try:
                        delay = float(match.group(1))
                        # Only set if it's currently shorter or unset
                        if not provider.cool_down_until or (now + delay + 1.0) > provider.cool_down_until:
                            provider.cool_down_until = now + delay + 1.0
                            print(f"DEBUG: Smart 429 retryDelay: {delay}s for '{provider_name}'")
                    except:
                        pass
                
                # 4. Global generic fallback for any 429 where no delay was found
                if not provider.cool_down_until:
                    # Apply a safe default cooldown (e.g. 10 minutes)
                    provider.cool_down_until = now + 600
                    print(f"DEBUG: Generic 429 fallback cooling down '{provider_name}' for 600s")
                
                # Mark all models of this provider as potentially exhausted for immediate penalty
                for m in provider.models.values():
                    m.latency_window.append(9999.0) # Penalty

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
                # Adaptive 429 Cooldown check
                if provider.cool_down_until and now < provider.cool_down_until:
                    continue
                
                # Default Adaptive cooling: wait longer if it keeps failing
                last_check = provider.last_check_at or (now - 86400) # Default to older if None
                cool_down_period = self.base_cool_down * (2 ** (provider.retry_count - 1))
                if now - last_check >= cool_down_period:
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
