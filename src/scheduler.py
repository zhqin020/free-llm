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
                tag_match = True
                if profile and profile.candidate_tags:
                    if not set(profile.candidate_tags).intersection(set(model.tags or [])):
                        tag_match = False
                
                score = self._score(provider, model, tag_match)
                candidates.append((provider, model, score))

        return sorted(candidates, key=lambda x: x[2], reverse=True)

    def _score(self, provider: ProviderState, model: ModelState, tag_match: bool) -> float:
        score = 0.0
        
        # 0. API Key Validation
        if not provider.api_key or provider.api_key.startswith("YOUR_"):
            score -= 1000.0 # Massive penalty for missing/placeholder keys
            
        # 1. Base Score (Free priority)
        score += 20.0 if provider.free else 5.0
        score += 20.0 if model.free else 5.0
        
        # 2. Status Penalty
        if provider.status == "cooling_down":
            score -= 25.0 # Significant penalty to avoid using it unless necessary
            
        # 3. Quality Penalty (Error Rate)
        rate = model.error_rate
        score -= rate * 100.0
        
        # 4. Latency Penalty
        p99 = model.p99_latency_ms
        if p99 > 0:
            # Penalty based on latency, e.g., -1 point per 200ms
            score -= (p99 / 200.0)
            
        # 5. Task Match Bonus
        if tag_match:
            score += 15.0
            
        return score

    def select(self, task_type: str = "text") -> Optional[dict]:
        candidates = self._candidate_models(task_type)
        if not candidates:
            return None

        # Pick the best with some randomness or just the top one for now
        provider, model, score = candidates[0]
        return {
            "provider": provider.name,
            "model": model.id,
            "free": provider.free and model.free,
            "latency": model.last_latency_ms,
            "score": score
        }
