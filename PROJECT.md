# OfficePlane (working name) — v0.1 Spec + Repo Skeleton (Python)

> **Goal:** create a new era of agentic use for Office tools.
> OfficePlane is an **enterprise-grade runtime** that gives agents "hands" to **render, inspect, and later patch** Office artifacts without "rewrite the whole file" workflows.
>
> **Foundation:** a hardened LibreOffice pool (via `unoserver/unoconvert`) + PDF→image rendering (PyMuPDF).
> **North Star:** a durable, tool-based agent framework that can replace a human who uses Office apps for long-running tasks (4+ hours), with proofs, audit logs, and self-contained end-to-end testing.

---

## 1) What we're building (v0.1)

### v0.1 deliverable: "Render Plane"
A **Gotenberg-like** HTTP service that:
- accepts `PPTX/PPT` (extend to `DOCX/XLSX` soon),
- converts to a canonical **PDF**,
- renders **per-page images** (PNG/JPEG),
- returns a **manifest** (checksums, timings, versions),
- supports **inline** results (dev) or **artifact URLs** (prod),
- is built on a hardened LO pool (backpressure, timeouts, restarts),
- ships with **enterprise observability** (structured logs, Prometheus metrics).

### Designed-for enterprise
- Structured audit logs with `request_id`
- Metrics for latency, failures, pool readiness/restarts
- No "login / JWT / DB" requirements to run end-to-end
- Optional auth hooks later; **default is self-contained**

### Agentic testing approach
We want tests that don't get stuck on:
- auth/JWT,
- external DB,
- external cloud accounts,
- Office login dialogs.

So we ship:
- a **mock driver** (no LibreOffice required) for unit/E2E-in-process tests,
- a **real LibreOffice driver** for full fidelity E2E (runs in Docker),
- a tiny "agent workflow harness" that runs start→finish locally.

---

## 2) Repo layout

```
officeplane/
  src/officeplane/
    api/
      main.py
      routes.py
      middleware.py
      schemas.py
    core/
      limits.py
      checksums.py
      render.py
      versions.py
    drivers/
      base.py
      libreoffice_pool.py
      libreoffice_driver.py
      mock_driver.py
    storage/
      base.py
      local.py
    observability/
      logging.py
      metrics.py
  docker/
    Dockerfile
  scripts/
    run_dev.sh
    e2e_agent_demo.py
    load_test.py
  tests/
    test_health.py
    test_render_real_pptx.py
    test_render_docker.py
  pyproject.toml
  README.md
  PROJECT.md (this file)
```

---

## Notes / Next steps (post v0.1)

- Add async job endpoint for long-running tasks: `/render_async` → `job_id`.
- Add layout map extraction (text blocks + bounding boxes) for agent grounding.
- Add semantic patching for XLSX (table/where/column), with proofs and validations.
- Add driver adapters (MS Graph, Google Sheets) behind the same `OfficeDriver` interface.

---

## Enterprise guidance (do not ignore)

- Default runs without auth/DB; auth is **optional** and pluggable.
- Always include request IDs and audit-friendly logs.
- Never depend on interactive logins for E2E tests.
- Keep a mock driver to run CI reliably.
- Pin versions in Docker builds for determinism.
