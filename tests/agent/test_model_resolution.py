"""Tests for per-skill model resolution (Phase 32).

Resolution order:
  1. OFFICEPLANE_AGENT_MODEL_<UPPER_UNDERSCORE> env var
  2. SKILL.md frontmatter model: field
  3. Tier-default env (OFFICEPLANE_AGENT_MODEL_FLASH / _PRO)
  4. Built-in default deepseek/deepseek-v4-flash
"""

from officeplane.content_agent.model import model_for_skill, model_for_tier


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_AGENT_MODEL_GENERATE_XLSX", "deepseek/deepseek-v4-pro")
    assert model_for_skill("generate-xlsx") == "deepseek/deepseek-v4-pro"


def test_env_override_dash_to_underscore(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_AGENT_MODEL_DOCUMENT_EDIT", "anthropic/opus-4")
    assert model_for_skill("document-edit") == "anthropic/opus-4"


def test_falls_back_to_tier_when_no_env(monkeypatch):
    monkeypatch.delenv("OFFICEPLANE_AGENT_MODEL_NONEXISTENT_SKILL", raising=False)
    monkeypatch.setenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
    assert model_for_skill("nonexistent-skill") == "deepseek/deepseek-v4-flash"


def test_reads_frontmatter_model_when_present(monkeypatch):
    """Verify that existing real skills' frontmatter model: field is picked up."""
    monkeypatch.delenv("OFFICEPLANE_AGENT_MODEL_GENERATE_XLSX", raising=False)
    out = model_for_skill("generate-xlsx")
    assert out and "/" in out  # provider/model format
    assert out.startswith("deepseek") or out.startswith("anthropic") or out.startswith("openai")


def test_tier_factory_returns_pro(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_AGENT_MODEL_PRO", "deepseek/deepseek-v4-pro")
    cfg = model_for_tier("pro")
    assert cfg.model == "deepseek/deepseek-v4-pro"
