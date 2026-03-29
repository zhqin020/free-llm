import os
import pytest
from src.provider import ProviderRegistry, ProviderState, ModelState
from src.admin import sync_from_github

def test_sync_case_insensitive_merge(tmp_path):
    # Setup registry with lowercase provider
    reg = ProviderRegistry()
    p1 = ProviderState(name="openrouter", type="openrouter", api_key="REAL_KEY")
    reg.add_provider(p1)
    
    # Setup dummy repo with README containing MixedCase/UPPERCASE provider
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    readme = repo_dir / "README.md"
    readme.write_text("""
# Resources

### [OpenRouter](https://openrouter.ai)
- [Gemma](https://openrouter.ai/google/gemma)
""")
    
    # Sync
    sync_from_github(str(repo_dir), reg)
    
    # Verify
    assert len(reg.all_providers()) == 1
    p = reg.get_provider("openrouter")
    assert p is not None
    assert p.api_key == "REAL_KEY"
    assert "gemma" in p.models
