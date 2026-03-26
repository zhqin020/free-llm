import os
import re
import subprocess
from typing import List

from .provider import ProviderRegistry, ProviderState, ModelState


def parse_freellm_res_readme(path: str) -> List[ProviderState]:
    if not os.path.exists(path):
        return []

    providers = []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 一个简单解析：抓取大标题作为 provider 名称
    matches = re.findall(r"### \[(.*?)\]", content)
    for name in matches:
        providers.append(ProviderState(name=name, type=name.lower().replace(" ", "_"), free=True))

    return providers


def sync_from_github(repo_dir: str, registry: ProviderRegistry) -> dict:
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        subprocess.run(["git", "pull", "--ff-only"], check=True)
        providers = parse_freellm_res_readme(os.path.join(repo_dir, "README.md"))

        for p in providers:
            existing = registry.get_provider(p.name)
            if not existing:
                registry.add_provider(p)

        return {"synced": len(providers)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.chdir(old_cwd)
