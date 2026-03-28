---
name: setup-harness
description: Reconfigure the agent harness for this project. Detects project structure, updates harness.config.sh, and replaces placeholders.
argument-hint: [optional: skip detection and use these values]
---

Reconfigure the agent harness. Run if project structure changes.

## Steps

1. Detect project structure (backend dir, frontend dir, Docker service names)
2. Ask user to confirm values
3. Write `harness.config.sh`
4. Update `.claude/settings.json` permissions if needed
5. Run `./scripts/setup-hooks.sh` to install pre-commit hook
6. Print summary
