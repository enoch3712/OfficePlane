# Agentic ECM — Measurement-First Plan

> **Status:** Approved direction (2026-06-12). Measure before restructuring.
> **Method:** Research-grounded audit (Anthropic agent guidance) + full code audit of `src/officeplane/`.
> **Decision:** Build a measurement layer first; let the data drive the later restructure. No execution-path surgery yet.

---

## Part 1 — Diagnosis (conclusions)

The agentic ECM is **not badly architected — it is an incomplete migration.** The newer structured-handler + deterministic-renderer pattern is genuinely modern and correct. The problem: the public surface, the verification story, and the context layer are still the old/aspirational versions, three orchestrators coexist, and nothing measures whether the agent works well — so the marketing describes the half that isn't wired.

### Scorecard vs. 2025-26 research

| Lens | Verdict | Proof (file:line) | Best practice |
|------|---------|-------------------|---------------|
| Tool / execution model | ⚠️ Bifurcated; public path weak | `/api/generate` → deepagents `LocalShellBackend`, no tools/schemas, LLM writes throwaway Node scripts, unsandboxed shell, temp 0.7, `--yes` (`drivers.py:43`, `runner.py:196`, `config.py:20`). `/api/jobs` → `SkillExecutor` → typed schemas + JSON-only LLM + deterministic renderer (`skill_executor.py:113`, `generate-pptx/handler.py`). Same skill name → two engines by endpoint. | Structured described tools by default; shell/code-mode only for many-tool/large-payload paths **with a sandbox**. |
| Verification ("verified request") | ❌ Nominal; contradicted by code | `/verify` = LLM grades own work from 500-char/page summary (`management_routes.py:925-1048`). `/execute` claims atomic+rollback but `PlanExecutor` has no transaction/rollback/lock (`executor.py:69-114`). Workchestrator "VERIFIED" = hardcoded `0.82/0.28` heuristic (`workchestrator.py:424-438`). Only `citation-validator` verifies for real, off the intent path. | Verify checks environment state; separate generator from evaluator. Self-asserted `confidence=1.0` is the canonical anti-pattern. |
| Context engineering | ❌ Poor | All ~34 skill bodies injected every run (`prompts.py:77`); zero progressive disclosure. Summaries stored but never read into retrieval — RAG returns raw chunks (`rag.py` has no `summary` refs). No token budgeting/compaction. | Smallest high-signal token set; just-in-time retrieval by reference; progressive disclosure; compaction. |
| Orchestration | ⚠️ Redundant | Three orchestrators: `orchestration/pipeline.py`, `agentic/workchestrator.py`, `components/planning/executor.py`, plus the deepagents runner. Ingestion correctly deterministic. | Lowest rung that works; one orchestrator. |
| Evals | ❌ Absent | No golden sets, no judge, no success metric. Every test mocks the LLM. Token-cost columns never written; chat status hardcoded `"ok"` (`chat_routes.py:99`). | 20-50 realistic tasks; pass@k / pass^k; environment-state grading. |
| Skills surface | ⚠️ Half-real | 16/34 have handlers: 8 real (PII, categorize, citations, edit, xlsx, vector-search), 8 thin (generate family = LLM JSON passthrough). Canonical 12 ECM verbs mostly SKILL.md stubs. Frontmatter (name/description/schemas) is good. | Lean SKILL.md + sharp name/description + bundled deterministic scripts + progressive disclosure. |

**Thesis:** the right pattern exists but isn't finished, isn't measured, and isn't the default.

### Research sources
- Building effective agents — https://www.anthropic.com/engineering/building-effective-agents
- Effective context engineering — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Writing tools for agents — https://www.anthropic.com/engineering/writing-tools-for-agents
- Code execution with MCP — https://www.anthropic.com/engineering/code-execution-with-mcp
- Demystifying evals — https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Agent Skills — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

---

## Part 2 — Design: the measurement layer

**Load-bearing idea:** the **same verification code runs offline (eval harness) and inline (live verify gate)**. One implementation, two consumers — kills drift, makes "verified request" literally true on the handler path.

### Component 1 — Eval harness (`evals/`)
- Golden task set (start 20-30 → 50): request + source fixtures + expected outcome/rubric; include known failure cases.
- Runner: real model, isolated env per trial (ephemeral workspace + transaction-rolled-back DB).
- Three graders: deterministic (counts/fields/validity), LLM-as-judge (open-ended, per-dimension, "Unknown" escape), env-state (DB rows + file on disk).
- Metrics: pass@k, pass^k, per-skill success/latency/token-cost. Output: scored JSON + markdown.
- Opt-in (`python -m evals` / `pytest -m eval`); tiny smoke eval in CI on a cheap model.

### Component 2 — Real per-skill verification (`content_agent/verification/`)
- `Verifier` protocol → `VerificationResult{passed, checks[], confidence|None, evidence}`. Confidence `None` unless computed — no fake `1.0`.
- Wired into the handler return path (Path B): generate-* assert artifact opens + element count vs request and **fail loudly on truncation** (current silent-truncation bug); extract asserts fields; redact re-scans for residual PII; export asserts valid + format.
- `/api/documents/{id}/verify` runs the registered verifiers + `citation-validator`, returns real evidence.

### Component 3 — Honest telemetry
- Populate `SkillInvocation.promptTokens/completionTokens` from LiteLLM usage (`persistence.py:40-50` drops them today).
- Derive real `status` from verification result; stop hardcoding `"ok"` (`chat_routes.py:99`).
- Add `SKILL_INVOKED` enum; fix the `SYSTEM_STARTUP` mislabel (`skill_executor.py:226`).
- Extend `observability/metrics.py` with per-skill success/failure counters, latency histogram, cost; surface at `/api/metrics`.

### Non-goals (wait for the data)
Not retiring the shell agent, not collapsing the orchestrators, not rerouting `/api/generate`, not implementing missing ECM verbs. The eval set reveals which matter.

---

## Part 3 — Next steps (sequenced)

Ordered for fastest signal first. Each task lists files + acceptance. Phases 1-3 ship the measurement layer; Phase 4 is the decision gate that unlocks the deferred restructure.

### Phase 0 — Scaffolding
- [ ] **0.1 Verifier protocol** — Create `src/officeplane/content_agent/verification/__init__.py` with `VerificationResult` dataclass + `Verifier` protocol. *Accept:* importable; unit test instantiates a result with `confidence=None`.
- [ ] **0.2 Evals package skeleton** — Create `evals/__init__.py`, `evals/tasks/` (data dir), `evals/runner.py` stub, `evals/graders/__init__.py`. Add `eval` marker to `pyproject.toml` pytest config. *Accept:* `python -m evals --list` runs and prints "0 tasks".

### Phase 1 — Honest telemetry (fast wins, no model)
- [ ] **1.1 Record token cost** — In `content_agent/persistence.py:40-50`, write `promptTokens`/`completionTokens` from the LiteLLM `usage` on the response. Thread usage out of `skill_executor.py`. *Accept:* a skill run writes non-null token columns; unit test asserts they're populated.
- [ ] **1.2 Fix audit eventType** — Add `SKILL_INVOKED` to the `event_type` enum (prisma migration) and use it at `skill_executor.py:226`. *Accept:* execution_history rows for skills read `SKILL_INVOKED`, not `SYSTEM_STARTUP`.
- [ ] **1.3 Honest chat status** — `chat_routes.py:99`: derive `status` from grounding/verification, not hardcoded `"ok"`. *Accept:* ungrounded fallback path logs a non-"ok" status; test covers both branches.
- [ ] **1.4 Per-skill metrics** — Extend `observability/metrics.py` with `skill_invocations_total{skill,status}`, `skill_duration_seconds{skill}`, `skill_tokens_total{skill}`. Increment in the skill-execution path. *Accept:* `/api/metrics` shows per-skill series after a run.

### Phase 2 — Real per-skill verifiers (deterministic, wired into handlers)
- [ ] **2.1 generate-* element-count + truncation** — Verifier asserts rendered artifact opens and slide/section count matches request; **fail (not silent-pass) on truncation**. Wire into generate-pptx/docx/pdf/xlsx handlers. *Accept:* requesting 20 slides but rendering 8 returns `passed=false` with evidence; unit tests with fixture artifacts.
- [ ] **2.2 extract field verifier** — Assert required fields present + typed. *Accept:* missing field → `passed=false`.
- [ ] **2.3 redact residual-PII verifier** — Re-scan output for PII regex hits; assert zero. *Accept:* leftover SSN → `passed=false`.
- [ ] **2.4 export validity verifier** — Assert output is valid for the requested format (OOXML/PDF magic + opens). *Accept:* corrupt/empty → `passed=false`.
- [ ] **2.5 Real `/verify` endpoint** — `management_routes.py` verify handler runs the registered verifiers + `citation-validator`, returns `VerificationResult` evidence instead of an LLM self-report. *Accept:* response carries real per-check evidence; confidence is `None` where not computed.

### Phase 3 — Eval harness
- [ ] **3.1 Golden tasks (first 10)** — Author 10 task files under `evals/tasks/` spanning generate-pptx, generate-docx, extract, detect-pii, vector-search, document-edit, with source fixtures and expected outcomes. *Accept:* `python -m evals --list` shows 10.
- [ ] **3.2 Isolated runner** — Execute each task via `SkillExecutor` against the real model in an ephemeral workspace + rolled-back DB transaction. *Accept:* a single task runs end-to-end and produces a raw result.
- [ ] **3.3 Graders** — Deterministic (reuse Phase-2 verifiers), env-state (assert DB rows), LLM-judge (per-dimension, "Unknown" escape). *Accept:* each grader scores a known pass and a known fail correctly.
- [ ] **3.4 Report + metrics** — Emit scored JSON + markdown: per-skill pass@k/pass^k, latency, token cost. *Accept:* `python -m evals` writes `evals/report.md` with a scorecard.
- [ ] **3.5 CI smoke eval** — 1-2 tasks on a cheap model, run in CI to catch harness regressions. *Accept:* CI job green; full eval stays opt-in.

### Phase 4 — Read the data, then decide (gate)
- [ ] **4.1 Baseline run** — Run the full eval set; record per-skill pass^k, cost, latency as the baseline.
- [ ] **4.2 Decision memo** — From the data, rank the deferred restructure work by measured impact: shell-agent retirement, orchestrator consolidation, `/api/generate` rerouting, missing ECM verbs, context/summaries wiring. Write `docs/superpowers/specs/<date>-ecm-restructure-decision.md`.
- [ ] **4.3 Spec the top item** — Take the highest-impact finding into its own brainstorm → spec → plan.

---

## Appendix — deferred items (from earlier prod-readiness audit, not in this plan)
These remain open but are tracked separately in `2026-06-11-production-readiness.md`: agent shell sandboxing, `/api/jobs/run` validation, CORS lockdown, API-key auth, key rotation, harness tooling in-container, `task_queue.py` split. Phase 1.x telemetry here overlaps with that plan's observability goals; coordinate so they don't double-implement.
