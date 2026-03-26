import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import load_config
from .provider import ProviderRegistry, ProviderState, ModelState
from .health import HealthManager
from .scheduler import Scheduler
from .router import Router
from .admin import sync_from_github

app = FastAPI(title="FreeLLM Router")


class ChatRequest(BaseModel):
    model: str = "adaptive"
    messages: list
    task_type: str = "text"


class ProviderAction(BaseModel):
    provider: str
    action: str


cfg = load_config(os.path.join(os.path.dirname(__file__), "../config.yaml")) if os.path.exists(os.path.join(os.path.dirname(__file__), "../config.yaml")) else None

registry = ProviderRegistry()
for p in (cfg.providers if cfg else []):
    provider_state = ProviderState(name=p.name, type=p.type, free=p.free, api_key=p.api_key)
    for m in p.models:
        provider_state.models[m.id] = ModelState(id=m.id, tags=m.tags, free=m.free)
    provider_state.status = "healthy"
    registry.add_provider(provider_state)

health_manager = HealthManager(registry, config=(cfg.scheduler.eviction if cfg else {}))
scheduler = Scheduler(registry, cfg.task_profiles if cfg else {}, cfg.scheduler.__dict__ if cfg else {})
router = Router(registry, health_manager, scheduler)


@app.get("/v1/providers")
def list_providers():
    return [
        {
            "name": p.name,
            "type": p.type,
            "free": p.free,
            "status": p.status,
            "models": [
                {
                    "id": m.id,
                    "tags": m.tags,
                    "free": m.free,
                    "error_rate": m.error_rate,
                    "last_latency_ms": m.last_latency_ms,
                }
                for m in p.models.values()
            ],
        }
        for p in registry.all_providers()
    ]


@app.post("/v1/chat/completions")
def create_completion(req: ChatRequest):
    health_manager.evaluate()
    result = router.route_request(req.task_type, req.messages[-1]["content"] if req.messages else "", **req.dict())
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/admin/providers/sync")
def sync_providers():
    root_path = os.path.join(os.path.dirname(__file__), "../freellm-res")
    if not os.path.exists(root_path):
        root_path = os.path.join(os.path.dirname(__file__), "../../freellm-res")

    result = sync_from_github(root_path, registry)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/admin/providers/action")
def provider_action(action: ProviderAction):
    prov = registry.get_provider(action.provider)
    if not prov:
        raise HTTPException(status_code=404, detail="provider not found")
    if action.action == "disable":
        prov.status = "unstable"
    elif action.action == "enable":
        prov.status = "healthy"
    else:
        raise HTTPException(status_code=400, detail="unknown action")
    return {"provider": prov.name, "status": prov.status}
