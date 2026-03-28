"""
Skills package — self-contained agent pipelines.

Each skill bundles its own system prompt, tools, driver preference,
validation logic, and optional quality-check pass.

Import `registry` to discover or invoke skills:

    from officeplane.skills import registry
    skill = registry.get("generate-pptx-quality")
"""

from officeplane.skills import registry  # noqa: F401 — triggers auto-registration
