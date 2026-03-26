import os
import re
import subprocess
from typing import List

from .provider import ProviderRegistry, ProviderState, ModelState


def parse_freellm_res_readme(path: str) -> List[ProviderState]:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    providers = []
    
    # Split by ### headers to get sections for each provider
    sections = re.split(r'\n### ', content)
    
    for section in sections[1:]:
        lines = section.strip().split('\n')
        if not lines:
            continue
        header_line = lines[0]
        
        # Parse provider name and URL: [Name](URL) or Name
        match = re.match(r'\[(.*?)\]\((.*?)\)', header_line)
        if match:
            name, url = match.groups()
        else:
            name = header_line.strip()
            url = ""
            
        provider = ProviderState(
            name=name,
            type=name.lower().replace(" ", "_"),
            url=url,
            free=True,
            status="healthy"
        )
        
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
        for m_name, m_url in bullet_links:
            if "openrouter.ai" in m_url:
                parts = m_url.split("openrouter.ai/")
                m_id = parts[1] if len(parts) > 1 else m_url.split("/")[-1]
            else:
                m_id = m_url
            provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
            
        # 3. Catch simple bullet models: - Name
        simple_bullets = re.findall(r'^- (?!\[)(.*)', section, re.MULTILINE)
        for m_name in simple_bullets:
            m_name = m_name.strip()
            if m_name and not m_name.startswith("Various") and not m_name.startswith("http"):
                m_id = m_name
                provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
                
        # 4. Catch table models and their quotas
        table_rows = re.findall(r'<tr><td>(.*?)</td><td>(.*?)</td></tr>', section, re.S)
        for m_name, m_limits in table_rows:
            m_name = re.sub(r'<.*?>', '', m_name).strip()
            if m_name and m_name != "Model Name":
                m_id = m_name
                provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
                # If provider has no global quota, try to take from first model
                if provider.max_quota_min == 0 or provider.max_quota_day == 0:
                    tm, td = parse_quota(m_limits)
                    if provider.max_quota_min == 0: provider.max_quota_min = tm
                    if provider.max_quota_day == 0: provider.max_quota_day = td
                
        providers.append(provider)

    return providers


def sync_from_github(repo_dir: str, registry: ProviderRegistry, db = None) -> dict:
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        # Only pull if it's a git repo
        if os.path.exists(".git"):
            subprocess.run(["git", "pull", "--ff-only"], check=True)
        
        readme_path = os.path.join(repo_dir, "README.md")
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
                # Update models for existing provider
                for m_id, model in p.models.items():
                    if m_id not in existing.models:
                        existing.models[m_id] = model
                
                # Update URL if remote has one
                if p.url:
                    existing.url = p.url
                
                # Update Quotas if remote has them and they aren't set locally
                # Or just always update if they are zero locally
                if p.max_quota_min > 0 and existing.max_quota_min == 0:
                    existing.max_quota_min = p.max_quota_min
                if p.max_quota_day > 0 and existing.max_quota_day == 0:
                    existing.max_quota_day = p.max_quota_day

                # Update name to proper case if it's currently lowecase
                if existing.name.islower() and not p.name.islower():
                    existing.name = p.name
                
                # Save back to DB to persist new models, URL and Quotas
                if db: db.save_provider(existing)

        return {"synced_providers": len(providers), "total_providers": len(registry.all_providers())}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}
    finally:
        os.chdir(old_cwd)
