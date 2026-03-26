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
            free=True,
            status="healthy"
        )
        
        # 1. Catch bullet models with links: - [Name](URL)
        bullet_links = re.findall(r'^- \[(.*?)\]\((.*?)\)', section, re.MULTILINE)
        for m_name, m_url in bullet_links:
            if "openrouter.ai" in m_url:
                m_id = m_url.split("/")[-1]
            else:
                m_id = m_url
            provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
            
        # 2. Catch simple bullet models: - Name
        simple_bullets = re.findall(r'^- (?!\[)(.*)', section, re.MULTILINE)
        for m_name in simple_bullets:
            m_name = m_name.strip()
            if m_name and not m_name.startswith("Various") and not m_name.startswith("http"):
                m_id = m_name
                provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
                
        # 3. Catch table models
        table_rows = re.findall(r'<tr><td>(.*?)</td><td>(.*?)</td></tr>', section, re.S)
        for m_name, m_limits in table_rows:
            m_name = re.sub(r'<.*?>', '', m_name).strip()
            if m_name and m_name != "Model Name":
                m_id = m_name
                provider.models[m_id] = ModelState(id=m_id, tags=[], free=True)
                
        providers.append(provider)

    return providers


def sync_from_github(repo_dir: str, registry: ProviderRegistry) -> dict:
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
            else:
                # Update models for existing provider
                for m_id, model in p.models.items():
                    if m_id not in existing.models:
                        existing.models[m_id] = model

        return {"synced_providers": len(providers), "total_providers": len(registry.all_providers())}
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.chdir(old_cwd)
