from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelState:
    id: str
    tags: List[str] = field(default_factory=list)
    free: bool = True
    last_latency_ms: Optional[float] = None
    success_count: int = 0
    error_count: int = 0

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
    status: str = "unknown"  # healthy, unstable, retry
    last_check_ms: Optional[float] = None

    @property
    def p99_latency_ms(self) -> float:
        # stub for now
        latencies = [m.last_latency_ms for m in self.models.values() if m.last_latency_ms is not None]
        if not latencies:
            return 0
        return sorted(latencies)[int(len(latencies) * 0.99) - 1] if len(latencies) > 0 else 0

    @property
    def average_error_rate(self) -> float:
        errs = [m.error_rate for m in self.models.values()]
        return sum(errs) / len(errs) if errs else 0.0


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
