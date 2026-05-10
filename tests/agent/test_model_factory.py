"""Tests for the LiteLLM-backed model factory."""

from __future__ import annotations

import os

import pytest

from officeplane.content_agent.model import (
    ModelConfig,
    build_chat_model,
    model_config_from_env,
)


def test_build_model_deepseek_string() -> None:
    cfg = ModelConfig(model="deepseek/deepseek-v4-flash", temperature=0.0)
    model = build_chat_model(cfg)
    assert model is not None
    assert getattr(model, "model", "").startswith("deepseek/")


def test_build_model_openai_string() -> None:
    cfg = ModelConfig(model="openai/gpt-4o-mini", temperature=0.0)
    model = build_chat_model(cfg)
    assert model is not None
    assert "gpt-4o-mini" in getattr(model, "model", "")


def test_build_model_rejects_empty() -> None:
    with pytest.raises(ValueError):
        build_chat_model(ModelConfig(model=""))


def test_model_config_from_env_defaults_to_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OFFICEPLANE_AGENT_MODEL", raising=False)
    monkeypatch.delenv("OFFICEPLANE_AGENT_TEMPERATURE", raising=False)
    cfg = model_config_from_env()
    assert cfg.model == "deepseek/deepseek-v4-flash"
    assert cfg.temperature == 0.0


def test_model_config_from_env_reads_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OFFICEPLANE_AGENT_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("OFFICEPLANE_AGENT_TEMPERATURE", "0.4")
    cfg = model_config_from_env()
    assert cfg.model == "openai/gpt-4o"
    assert cfg.temperature == pytest.approx(0.4)


def test_build_model_passes_max_tokens() -> None:
    cfg = ModelConfig(model="deepseek/deepseek-v4-flash", max_tokens=512)
    model = build_chat_model(cfg)
    assert getattr(model, "max_tokens", None) == 512
