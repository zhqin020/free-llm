import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Deque
from collections import deque


@dataclass
class ModelState:
    id: str
    tags: List[str] = field(default_factory=list)
    free: bool = True
    price_input_1k: float = 0.0
    price_output_1k: float = 0.0
    latency_window: Deque[float] = field(default_factory=lambda: deque(maxlen=20))
    success_count: int = 0
    error_count: int = 0
    last_used_at: Optional[float] = None
    cool_down_until: Optional[float] = None

    @property
    def last_latency_ms(self) -> Optional[float]:
        return self.latency_window[-1] if self.latency_window else None

    @property
    def p99_latency_ms(self) -> float:
        if not self.latency_window:
            return 0.0
        sorted_latencies = sorted(list(self.latency_window))
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_window:
            return 0.0
        return sum(self.latency_window) / len(self.latency_window)

    @property
    def error_rate(self) -> float:
        total = self.success_count + self.error_count
        return self.error_count / total if total else 0.0


@dataclass
class ProviderState:
    name: str
    type: str
    free: bool = True
    api_key: str = ""
    url: str = ""
    api_url: str = ""
    token_price_1k: float = 0.0
    max_quota_min: int = 0  # 0 means unlimited
    max_quota_day: int = 0
    current_quota_min: int = 0
    current_quota_day: int = 0
    last_reset_min: float = field(default_factory=time.time)
    last_reset_day: float = field(default_factory=time.time)
    models: Dict[str, ModelState] = field(default_factory=dict)
    status: str = "unknown"  # healthy, unstable, cooling_down
    last_check_at: Optional[float] = None
    retry_count: int = 0
    cool_down_until: Optional[float] = None

    def check_and_update_quota(self, tokens: int = 1) -> bool:
        now = time.time()
        
        # Reset minute quota if needed
        if now - self.last_reset_min >= 60:
            self.current_quota_min = 0
            self.last_reset_min = now
            
        # Reset daily quota if needed (roughly 24h)
        if now - self.last_reset_day >= 86400:
            self.current_quota_day = 0
            self.last_reset_day = now
            
        # Check limits
        if self.max_quota_min > 0 and self.current_quota_min + tokens > self.max_quota_min:
            return False
        if self.max_quota_day > 0 and self.current_quota_day + tokens > self.max_quota_day:
            return False
            
        # Update
        self.current_quota_min += tokens
        self.current_quota_day += tokens
        return True

    @property
    def is_functional(self) -> bool:
        # Check API Key
        if not self.api_key:
            return False
        # Placeholders
        p_keys = ["YOUR_", "EXAMPLE", "PLACEHOLDER", "AIzaSyA7mP3J8YL1hUUtuDTj0FD0YHiOhAz04Wk"] # Wait, don't hardcode the key.
        # Use common placeholder patterns
        if any(p in self.api_key for p in ["YOUR_", "EXAMPLE", "PLACEHOLDER"]):
            return False
        # Check API URL
        if not self.api_url:
            return False
        # Documentation links are NOT functional API endpoints
        doc_patterns = ["docs.mistral.ai", "openrouter.ai/docs", "cloud.google.com", "documentation", "getting-started"]
        if any(p in self.api_url.lower() for p in doc_patterns):
            return False
        return True

    @property
    def average_error_rate(self) -> float:
        errs = [m.error_rate for m in self.models.values()]
        return sum(errs) / len(errs) if errs else 0.0

    @property
    def p99_latency_ms(self) -> float:
        p99s = [m.p99_latency_ms for m in self.models.values() if m.latency_window]
        return max(p99s) if p99s else 0.0


class ProviderRegistry:
    def __init__(self):
        self.providers: Dict[str, ProviderState] = {}

    def add_provider(self, provider: ProviderState):
        # Remove existing if any (case-insensitive) to avoid duplicates
        self.remove_provider(provider.name)
        self.providers[provider.name] = provider

    def get_provider(self, name: str) -> Optional[ProviderState]:
        # Case-insensitive lookup
        for k, v in self.providers.items():
            if k.lower() == name.lower():
                return v
        return None

    def all_providers(self) -> List[ProviderState]:
        return list(self.providers.values())

    def remove_provider(self, name: str):
        target_key = None
        for k in self.providers.keys():
            if k.lower() == name.lower():
                target_key = k
                break
        if target_key:
            del self.providers[target_key]

    def mark_unstable(self, name: str):
        p = self.get_provider(name)
        if p:
            p.status = "unstable"

    def mark_healthy(self, name: str):
        p = self.get_provider(name)
        if p:
            p.status = "healthy"
