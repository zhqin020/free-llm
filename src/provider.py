import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Deque
from collections import deque


@dataclass
class ModelState:
    id: str
    tags: List[str] = field(default_factory=list)
    free: bool = True
    latency_window: Deque[float] = field(default_factory=lambda: deque(maxlen=20))
    success_count: int = 0
    error_count: int = 0
    last_used_at: Optional[float] = None

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
    models: Dict[str, ModelState] = field(default_factory=dict)
    status: str = "unknown"  # healthy, unstable, cooling_down
    last_check_at: Optional[float] = None
    retry_count: int = 0

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
        self.providers[provider.name] = provider

    def get_provider(self, name: str) -> Optional[ProviderState]:
        return self.providers.get(name)

    def all_providers(self) -> List[ProviderState]:
        return list(self.providers.values())

    def remove_provider(self, name: str):
        if name in self.providers:
            del self.providers[name]

    def mark_unstable(self, name: str):
        p = self.providers.get(name)
        if p:
            p.status = "unstable"

    def mark_healthy(self, name: str):
        p = self.providers.get(name)
        if p:
            p.status = "healthy"
