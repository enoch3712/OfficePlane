"""Tests for model_for_tier and tier-routed skill invocation (Phase 9)."""
from __future__ import annotations

import pytest

from officeplane.content_agent.model import model_for_tier


def test_default_tier_is_flash(monkeypatch):
    monkeypatch.delenv("OFFICEPLANE_AGENT_MODEL_FLASH", raising=False)
    monkeypatch.delenv("OFFICEPLANE_AGENT_MODEL_PRO", raising=False)
    cfg = model_for_tier("flash")
    assert "deepseek-v4-flash" in cfg.model


def test_pro_tier_picks_pro_model(monkeypatch):
    monkeypatch.delenv("OFFICEPLANE_AGENT_MODEL_PRO", raising=False)
    cfg = model_for_tier("pro")
    assert "deepseek-v4-pro" in cfg.model


def test_unknown_tier_falls_back_to_flash(monkeypatch):
    monkeypatch.delenv("OFFICEPLANE_AGENT_MODEL_FLASH", raising=False)
    cfg = model_for_tier("nonsense")
    assert "deepseek-v4-flash" in cfg.model
