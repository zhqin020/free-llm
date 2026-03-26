from typing import List, Optional

from .provider import ProviderRegistry, ProviderState, ModelState


class Scheduler:
    def __init__(self, registry: ProviderRegistry, task_profiles: dict, scheduler_config: dict):
        self.registry = registry
        self.task_profiles = task_profiles
        self.scheduler_config = scheduler_config

    def _candidate_models(self, task_type: str) -> List[tuple]:
        profile = self.task_profiles.get(task_type)
        candidates = []

        for provider in self.registry.all_providers():
            if provider.status == "unstable":
                continue
            for model in provider.models.values():
                if profile and profile.candidate_tags:
                    if not set(profile.candidate_tags).intersection(set(model.tags)):
                        continue
                score = self._score(provider, model)
                candidates.append((provider, model, score))

        return sorted(candidates, key=lambda x: x[2], reverse=True)

    def _score(self, provider: ProviderState, model: ModelState) -> float:
        score = 0.0
        score += 1.0 if provider.free else 0.5
        score += 1.0 if model.free else 0.5

        rate = model.error_rate
        score -= rate * 5

        latency = model.last_latency_ms or 1000
        score -= latency / 1000.0

        return score

    def select(self, task_type: str = "text") -> Optional[dict]:
        candidates = self._candidate_models(task_type)
        if not candidates:
            return None

        provider, model, _ = candidates[0]
        return {
            "provider": provider.name,
            "model": model.id,
            "free": provider.free and model.free,
            "latency": model.last_latency_ms,
        }
