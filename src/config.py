import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ModelConfig:
    id: str
    tags: List[str] = field(default_factory=list)
    free: bool = True


@dataclass
class ProviderConfig:
    name: str
    type: str
    api_key: str
    free: bool = True
    models: List[ModelConfig] = field(default_factory=list)


@dataclass
class SchedulerConfig:
    strategy: str = "adaptive"
    max_retries: int = 3
    timeout_seconds: int = 20
    eviction: Dict[str, Any] = field(default_factory=lambda: {
        "error_rate": 0.2,
        "p90_latency_ms": 1200,
        "cool_down_sec": 300,
    })


@dataclass
class TaskProfile:
    priority: List[str] = field(default_factory=list)
    candidate_tags: List[str] = field(default_factory=list)


@dataclass
class RouterConfig:
    providers: List[ProviderConfig] = field(default_factory=list)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    task_profiles: Dict[str, TaskProfile] = field(default_factory=dict)


def load_config(path: str) -> RouterConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    providers = []
    for p in raw.get("providers", []):
        models = [ModelConfig(**m) for m in p.get("models", [])]
        providers.append(ProviderConfig(
            name=p["name"],
            type=p.get("type", p.get("name", "unknown")),
            api_key=p.get("api_key", ""),
            free=p.get("free", True),
            models=models,
        ))

    scheduler = SchedulerConfig(**raw.get("scheduler", {}))
    task_profiles = {k: TaskProfile(**v) for k, v in raw.get("task_profiles", {}).items()}

    return RouterConfig(providers=providers, scheduler=scheduler, task_profiles=task_profiles)
