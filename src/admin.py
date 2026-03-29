import os
import re
import subprocess
from typing import List

import requests
from .provider import ProviderRegistry, ProviderState, ModelState


def parse_freellm_res_readme(path: str) -> List[ProviderState]:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    providers = []
    
    # Split by ### headers at the start of a line
    sections = re.split(r'(?m)^###', content)
    
    for section in sections[1:]:
        lines = section.strip().split('\n')
        if not lines:
            continue
        header_line = lines[0]
        
        # Parse provider name and URL: [Name](URL) or Name
        # Handle optional markdown hashes (e.g. ### [Name](URL))
        match = re.match(r'(?:#+\s*)?\[(.*?)\]\((.*?)\)', header_line)
        if match:
            name, url = match.groups()
        else:
            name = re.sub(r'^#+\s*', '', header_line).strip()
            url = ""
            
        provider = ProviderState(
            name=name,
            type=name.lower().replace(" ", "_"),
            url=url,
            free=True,
            status="healthy"
        )
        
        # Detect if the URL is likely a documentation/registration page rather than an API endpoint
        # If it's a root domain or contains doc/console/app keywords, it's likely a doc page.
        parsed_url = re.sub(r'https?://', '', url.lower()).rstrip('/')
        is_root_domain = '/' not in parsed_url
        is_doc_url = is_root_domain or any(x in url.lower() for x in ["/docs", "/console", "/app/", "/build.", "docs.", "console.", "/explore", "developers.", "api-docs.", "cloud.", "marketplace.", "blog.", "support."])
        
        if "google_ai_studio" in provider.type or "google ai studio" in name.lower():
            provider.type = "google_ai_studio"
            provider.api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        elif "openrouter.ai" in url:
            provider.type = "openrouter"
            provider.api_url = "https://openrouter.ai/api/v1/chat/completions"
        elif "groq.com" in url:
            provider.type = "groq"
            provider.api_url = "https://api.groq.com/openai/v1/chat/completions"
        elif "mistral.ai" in url:
            provider.type = "mistral"
            provider.api_url = "https://api.mistral.ai/v1/chat/completions"
        elif "cohere.com" in url:
            provider.type = "cohere"
            provider.api_url = "https://api.cohere.com/v1/chat/completions"
        elif "cerebras.ai" in url:
            provider.type = "cerebras"
            provider.api_url = "https://api.cerebras.ai/v1/chat/completions"
        elif "nvidia.com" in url or "build.nvidia.com" in url:
            provider.type = "nvidia"
            provider.api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
        elif "huggingface.co" in url:
            provider.type = "huggingface"
            provider.api_url = "https://router.huggingface.co/v1/chat/completions"
        elif "github.com" in url:
            provider.type = "github"
            provider.api_url = "https://models.inference.ai.azure.com/chat/completions"
        elif "vercel.com" in url:
            provider.type = "vercel"
            provider.api_url = "https://gateway.ai.vercel.com/v1/chat/completions"
        elif is_doc_url:
            # If it looks like a doc URL, don't use it as API endpoint
            provider.api_url = None
        else:
            provider.api_url = url # Default to same if unknown
        
        # Parse name and URL...
        # ... (provider init)
        
        # Quota Parsing
        def parse_quota(text):
            min_match = re.search(r'([\d,]+)\s+requests/minute', text, re.I)
            day_match = re.search(r'([\d,]+)\s+requests/day', text, re.I)
            q_min = int(min_match.group(1).replace(',', '')) if min_match else 0
            q_day = int(day_match.group(1).replace(',', '')) if day_match else 0
            return q_min, q_day

        # 1. Global section quota
        s_min, s_day = parse_quota(section)
        provider.max_quota_min = s_min
        provider.max_quota_day = s_day

        # 2. Catch bullet models with links: - [Name](URL)
        bullet_links = re.findall(r'^- \[(.*?)\]\((.*?)\)', section, re.MULTILINE)
        not_model_keywords = ["overview", "console", "documentation", "pricing", "guide", "status", "build", "developers", "docs"]
        
        for m_name, m_url in bullet_links:
            # Skip if name or URL looks like documentation
            if any(k in m_name.lower() for k in not_model_keywords) or \
               any(k in m_url.lower() for k in ["/docs", "/console", "docs.", "console.", "/explore", "developers."]):
                continue
                
            if "openrouter.ai" in m_url:
                parts = m_url.split("openrouter.ai/")
                m_id = parts[1] if len(parts) > 1 else m_url.split("/")[-1]
                m_id = m_id.strip("/")
            elif "google.com" in m_url:
                # For Google links, the URL is usually a landing page, so use name
                m_id = m_name.lower().replace(" ", "-")
                m_id = "".join(c for c in m_id if c.isalnum() or c in "-./:")
            else:
                m_id = m_name 
            
            # Normalize m_id
            m_id = m_id.lower().replace(" ", "-")
            m_id = "".join(c for c in m_id if c.isalnum() or c in "-./:")
            if m_id:
                provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
            
        # 3. Catch simple bullet models: - Name
        simple_bullets = re.findall(r'^- (?!\[)(.*)', section, re.MULTILINE)
        for m_name in simple_bullets:
            m_name = m_name.strip()
            if m_name and not m_name.startswith("Various") and not m_name.startswith("http"):
                m_id = m_name.lower().replace(" ", "-")
                m_id = "".join(c for c in m_id if c.isalnum() or c in "-./:")
                if m_id:
                    provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
                
        # 4. Catch table models and their quotas
        table_rows = re.findall(r'<tr><td>(.*?)</td><td>(.*?)</td></tr>', section, re.S)
        for m_name, m_limits in table_rows:
            m_name = re.sub(r'<.*?>', '', m_name).strip()
            if m_name and m_name != "Model Name":
                m_id = m_name.lower().replace(" ", "-")
                m_id = "".join(c for c in m_id if c.isalnum() or c in "-./:")
                if m_id:
                    provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
                # If provider has no global quota, try to take from first model
                if provider.max_quota_min == 0 or provider.max_quota_day == 0:
                    tm, td = parse_quota(m_limits)
                    if provider.max_quota_min == 0: provider.max_quota_min = tm
                    if provider.max_quota_day == 0: provider.max_quota_day = td

        # 5. Add default models for major providers
        default_model_map = {
            "google_ai_studio": [
                "gemini-2.0-flash", 
                "gemini-2.0-flash-exp", 
                "gemini-1.5-flash", 
                "gemini-1.5-pro",
                "gemini-1.5-flash-latest"
            ],
            "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
            "mistral": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
            "cerebras": ["llama3.1-8b", "llama3.1-70b"],
            "opencode_zen": ["big-pickle", "minimax-m2.5"],
            "cohere": ["command-r-plus", "command-r"],
            "nvidia": ["meta/llama-3.1-405b-instruct", "meta/llama-3.1-70b-instruct", "nvidia/llama-3.1-nemotron-70b-instruct"],
            "sambanova": ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-70B-Instruct", "Meta-Llama-3.1-8B-Instruct", "DeepSeek-V3", "DeepSeek-R1-Distill-Llama-70B"]
        }
        
        for p_type, models in default_model_map.items():
            if p_type in provider.type or p_type in provider.name.lower():
                for m_id in models:
                    if m_id not in provider.models:
                        provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
                
        providers.append(provider)

    return providers


def sync_from_github(repo_dir: str, registry: ProviderRegistry, db = None) -> dict:
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        # Only pull if it's a git repo
        if os.path.exists(".git"):
            subprocess.run(["git", "pull", "--ff-only"], check=True)
        
        readme_path = "README.md"
        providers = parse_freellm_res_readme(readme_path)

        for p in providers:
            # Case-insensitive lookup
            existing = None
            for name, prov in registry.providers.items():
                if name.lower() == p.name.lower():
                    existing = prov
                    break
            
            if not existing:
                registry.add_provider(p)
                if db: db.save_provider(p)
            else:
                # Reconcile models: Preserve health data for models that still exist, 
                # but remove those no longer in the source README.
                current_models = {}
                for m_id, model in p.models.items():
                    if m_id in existing.models:
                        # Carry over health stats/tags if they exist
                        old_m = existing.models[m_id]
                        model.tags = list(set(model.tags + (old_m.tags or [])))
                        model.latency_window = old_m.latency_window
                        model.success_count = old_m.success_count
                        model.error_count = old_m.error_count
                        model.last_used_at = old_m.last_used_at
                    current_models[m_id] = model
                existing.models = current_models
                
                # Update URLs if remote has one
                if p.url:
                    existing.url = p.url
                if p.api_url and not existing.api_url:
                    existing.api_url = p.api_url
                
                # Update Quotas if remote has them and they aren't set locally
                if p.max_quota_min > 0 and existing.max_quota_min == 0:
                    existing.max_quota_min = p.max_quota_min
                if p.max_quota_day > 0 and existing.max_quota_day == 0:
                    existing.max_quota_day = p.max_quota_day

                # Update name to proper case if it's currently lowercase
                if existing.name.islower() and not p.name.islower():
                    existing.name = p.name
                
                # Save back to DB to persist new model list, URL and Quotas
                if db: 
                    # We need to wipe old models for this provider in DB first 
                    # delete_provider wipes both provider and its models
                    db.delete_provider(existing.name)
                    db.save_provider(existing)

        return {"synced_providers": len(providers), "total_providers": len(registry.all_providers())}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}
    finally:
        os.chdir(old_cwd)


def probe_provider_models(provider_name: str, registry: ProviderRegistry, db=None) -> dict:
    prov = registry.get_provider(provider_name)
    if not prov:
        return {"error": "Provider not found"}
    
    if not prov.api_key or any(p in prov.api_key for p in ["YOUR_", "EXAMPLE", "PLACEHOLDER"]):
        return {"error": "Missing or placeholder API key. Please set a valid key first."}

    # Heuristic: If api_url is a doc link, try to guess the API base
    candidate_urls = []
    current_url = prov.api_url.lower()
    
    # Common mappings
    if "groq.com" in current_url or "groq" in prov.name.lower():
        candidate_urls.append("https://api.groq.com/openai/v1")
    elif "mistral.ai" in current_url or "mistral" in prov.name.lower():
        candidate_urls.append("https://api.mistral.ai/v1")
    elif "openrouter.ai" in current_url:
        candidate_urls.append("https://openrouter.ai/api/v1")
    elif "deepseek" in prov.name.lower():
        candidate_urls.append("https://api.deepseek.com")
    elif "siliconflow" in prov.name.lower():
        candidate_urls.append("https://api.siliconflow.cn/v1")
    elif "huggingface" in prov.name.lower() or "huggingface.co" in current_url:
        candidate_urls.append("https://router.huggingface.co/v1")
    elif "github" in prov.name.lower() or "azure.com" in current_url:
        candidate_urls.append("https://models.inference.ai.azure.com")
    elif "novita" in prov.name.lower():
        candidate_urls.append("https://api.novita.ai/v3/openai")
    elif "fireworks" in prov.name.lower():
        candidate_urls.append("https://api.fireworks.ai/inference/v1")
    
    # Generic strip of /chat/completions
    base_api = prov.api_url
    if "/chat/completions" in base_api:
        base_api = base_api.replace("/chat/completions", "")
    
    # Special adjustment for Google: they use /openai/v1/models if base is /openai/
    if "generativelanguage.googleapis.com" in base_api and "/openai" in base_api:
        candidate_urls.append(base_api.rstrip('/') + "/v1")
    
    candidate_urls.append(base_api.rstrip('/'))

    errors = []
    for base_url in list(dict.fromkeys(candidate_urls)): # Unique preserving order
        if not base_url or not base_url.startswith("http"):
            continue
        probe_url = f"{base_url.rstrip('/')}/models"
        try:
            headers = {"Authorization": f"Bearer {prov.api_key}"}
            # OpenRouter requires special header sometimes, but Bearer usually works
            resp = requests.get(probe_url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                # OpenAI format usually has {"data": [{"id": "..."}]}
                models_list = data.get("data", [])
                if not models_list and isinstance(data, list): # Some providers return a list directly
                    models_list = data
                
                new_count = 0
                discovered = []
                for m in models_list:
                    m_id = m.get("id") if isinstance(m, dict) else str(m)
                    if m_id and m_id not in prov.models:
                        prov.models[m_id] = ModelState(id=m_id, tags=["discovered"])
                        new_count += 1
                        discovered.append(m_id)
                
                # Update api_url to a working one if it was a doc link
                if "docs" in prov.api_url or "getting-started" in prov.api_url or not prov.api_url:
                    prov.api_url = f"{base_url}/chat/completions"
                
                if db: db.save_provider(prov)
                return {
                    "status": "success", 
                    "base_url": base_url,
                    "discovered_count": new_count, 
                    "total_count": len(prov.models),
                    "new_models": discovered
                }
            else:
                errors.append(f"{base_url}: {resp.status_code}")
        except Exception as e:
            errors.append(f"{base_url}: {str(e)}")

    return {"error": "Could not discover models", "details": errors}
