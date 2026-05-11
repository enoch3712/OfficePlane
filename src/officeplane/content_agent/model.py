"""LiteLLM-backed chat model factory.

Provider-agnostic. Pass a `provider/model` string (e.g. ``deepseek/deepseek-chat``,
``openai/gpt-4o-mini``, ``gemini/gemini-2.5-pro``, ``anthropic/claude-opus-4-7``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_litellm import ChatLiteLLM


@dataclass
class ModelConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout: int = 120
    api_base: str | None = None
    api_key: str | None = None


def build_chat_model(cfg: ModelConfig) -> ChatLiteLLM:
    if not cfg.model:
        raise ValueError(
            "ModelConfig.model is required (e.g. 'deepseek/deepseek-chat')"
        )

    kwargs: dict[str, object] = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "request_timeout": cfg.timeout,
    }
    if cfg.max_tokens is not None:
        kwargs["max_tokens"] = cfg.max_tokens
    if cfg.api_base:
        kwargs["api_base"] = cfg.api_base
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key

    return ChatLiteLLM(**kwargs)


DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_MODEL_FLASH = "deepseek/deepseek-v4-flash"
DEFAULT_MODEL_PRO = "deepseek/deepseek-v4-pro"


def model_config_from_env() -> ModelConfig:
    return ModelConfig(
        model=os.getenv("OFFICEPLANE_AGENT_MODEL", DEFAULT_MODEL),
        temperature=float(os.getenv("OFFICEPLANE_AGENT_TEMPERATURE", "0.0")),
        timeout=int(os.getenv("OFFICEPLANE_AGENT_TIMEOUT", "120")),
    )


def model_for_skill(skill_name: str, *, fallback_tier: str = "flash") -> str:
    """Resolve the model string for a given skill, honouring:

      1) env OFFICEPLANE_AGENT_MODEL_<UPPER_UNDERSCORE> (e.g. GENERATE_XLSX)
      2) the skill's frontmatter model: field (looked up via skill_loader)
      3) fallback_tier env (OFFICEPLANE_AGENT_MODEL_FLASH / _PRO)
      4) built-in default deepseek/deepseek-v4-flash

    Returns the LiteLLM model string (e.g. "deepseek/deepseek-v4-pro").
    """
    env_key = "OFFICEPLANE_AGENT_MODEL_" + skill_name.upper().replace("-", "_")
    env_override = os.getenv(env_key)
    if env_override:
        return env_override

    # Frontmatter lookup (lazy import to avoid circular dependency)
    try:
        from pathlib import Path  # noqa: PLC0415

        from officeplane.content_agent.skill_loader import discover_skills  # noqa: PLC0415

        skills_root = Path(__file__).resolve().parent / "skills"
        for s in discover_skills(skills_root):
            if s.name == skill_name and s.model:
                return s.model
    except Exception:  # noqa: BLE001
        pass

    # Tier fallback
    return model_for_tier(fallback_tier).model


def model_for_tier(tier: str = "flash") -> ModelConfig:
    """Return a ModelConfig for the given tier ('flash' or 'pro').

    Falls back to 'flash' for any unrecognised tier string.
    Model strings are overridable via env vars:
        OFFICEPLANE_AGENT_MODEL_FLASH  (default: deepseek/deepseek-v4-flash)
        OFFICEPLANE_AGENT_MODEL_PRO    (default: deepseek/deepseek-v4-pro)
    """
    temperature = float(os.getenv("OFFICEPLANE_AGENT_TEMPERATURE", "0.0"))
    if tier == "pro":
        return ModelConfig(
            model=os.getenv("OFFICEPLANE_AGENT_MODEL_PRO", DEFAULT_MODEL_PRO),
            temperature=temperature,
        )
    # Default: flash (also handles any unknown tier)
    return ModelConfig(
        model=os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", DEFAULT_MODEL_FLASH),
        temperature=temperature,
    )
