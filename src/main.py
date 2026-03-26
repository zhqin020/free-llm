import os
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .config import load_config
from .provider import ProviderRegistry, ProviderState, ModelState
from .health import HealthManager
from .scheduler import Scheduler
from .router import Router
from .admin import sync_from_github

from .database import DatabaseManager

app = FastAPI(title="FreeLLM Router")

# Models for OpenAI compatibility
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = "adaptive"
    messages: List[ChatMessage]
    task_type: str = "text"
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_retries: int = 3

class ProviderAction(BaseModel):
    provider: str
    action: str

# Globals
DB_PATH = os.path.join(os.path.dirname(__file__), "../freellm.db")
db = DatabaseManager(DB_PATH)

registry = ProviderRegistry()

# Load from DB
for p in db.load_all_providers():
    registry.add_provider(p)

# Load additional config for managers
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config.yaml")
cfg = load_config(CONFIG_PATH) if os.path.exists(CONFIG_PATH) else None

health_manager = HealthManager(registry, config=cfg.scheduler.eviction if cfg else {})
scheduler = Scheduler(registry, 
                      task_profiles={k: vars(v) for k, v in cfg.task_profiles.items()} if cfg else {},
                      scheduler_config=vars(cfg.scheduler) if cfg else {})
router = Router(registry, health_manager, scheduler)

@app.on_event("startup")
async def startup_event():
    # Check for placeholder keys
    for p in registry.all_providers():
        if p.api_key.startswith("YOUR_"):
            print(f"WARNING: Provider '{p.name}' is using a placeholder API key and will be deprioritized.")

    # Start background health evaluation
    async def periodic_health_check():
        while True:
            health_manager.evaluate()
            # Save health results back to DB
            for p in registry.all_providers():
                db.save_provider(p)
            await asyncio.sleep(60) # Every minute
    
    asyncio.create_task(periodic_health_check())

class ProviderUpdate(BaseModel):
    name: str
    api_key: Optional[str] = None
    url: Optional[str] = None
    token_price_1k: Optional[float] = None
    max_quota_min: Optional[int] = None
    max_quota_day: Optional[int] = None

@app.post("/admin/providers/update")
async def update_provider(upd: ProviderUpdate):
    p = registry.get_provider(upd.name)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if upd.api_key is not None: p.api_key = upd.api_key
    if upd.url is not None: p.url = upd.url
    if upd.token_price_1k is not None: p.token_price_1k = upd.token_price_1k
    if upd.max_quota_min is not None: p.max_quota_min = upd.max_quota_min
    if upd.max_quota_day is not None: p.max_quota_day = upd.max_quota_day
    
    db.save_provider(p)
    return {"status": "success", "provider": p.name}


@app.get("/", response_class=HTMLResponse)
async def read_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static/index.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>FreeLLM Router</h1><p>Dashboard file not found at src/static/index.html</p>"


@app.get("/v1/models")
def list_models():
    models = []
    for p in registry.all_providers():
        for m in p.models.values():
            models.append({
                "id": m.id,
                "object": "model",
                "owned_by": p.name,
                "permission": [],
                "free": m.free,
                "tags": m.tags,
                "status": p.status
            })
    return {"object": "list", "data": models}


@app.get("/v1/providers")
def list_providers():
    return [
        {
            "name": p.name,
            "type": p.type,
            "free": p.free,
            "api_key": p.api_key if p.api_key else "",
            "url": p.url if p.url else "",
            "token_price_1k": p.token_price_1k,
            "max_quota_min": p.max_quota_min,
            "max_quota_day": p.max_quota_day,
            "current_quota_min": p.current_quota_min,
            "current_quota_day": p.current_quota_day,
            "status": p.status,
            "retry_count": p.retry_count,
            "avg_error_rate": p.average_error_rate,
            "p99_latency": p.p99_latency_ms,
            "models": [
                {
                    "id": m.id,
                    "tags": m.tags,
                    "free": m.free,
                    "error_rate": m.error_rate,
                    "p99_latency": m.p99_latency_ms,
                    "avg_latency": m.avg_latency_ms,
                    "last_used": m.last_used_at,
                }
                for m in p.models.values()
            ],
        }
        for p in registry.all_providers()
    ]


@app.post("/v1/chat/completions")
async def create_completion(req: ChatRequest):
    # Minor sync before request
    health_manager.evaluate()
    
    # router.route_request now expects list of dicts for messages
    messages_dict = [m.dict() for m in req.messages]
    
    result = router.route_request(
        req.task_type, 
        messages_dict, 
        model=req.model,
        stream=req.stream,
        temperature=req.temperature,
        max_retries=req.max_retries
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/admin/providers/sync")
def sync_providers():
    res_path = os.path.join(os.path.dirname(__file__), "../freellm-res")
    if not os.path.exists(res_path):
         res_path = os.path.join(os.path.dirname(__file__), "../../freellm-res")

    result = sync_from_github(res_path, registry, db=db)
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
        prov.retry_count = 0
    else:
        raise HTTPException(status_code=400, detail="unknown action")
    
    return {"provider": prov.name, "status": prov.status}
