# Code + Architecture Review (2026-03-08)

## System Snapshot
- The repo is currently a script-centric invoice pipeline with strong parsing heuristics and good test coverage.
- Core Python CLIs are large monoliths:
  - `gmail_invoice_finder.py` ~1650 LOC
  - `graph_invoice_finder.py` ~1508 LOC
  - `invoices_report.py` ~2680 LOC
- Go API is a minimal health endpoint only.
- Local infra includes Postgres/RabbitMQ/n8n but application paths are mostly filesystem-based.

## Verified Baseline
- Tests: `159 passed` (`tests/` suite).
- Static typing is not production-ready: `mypy` reports 105 issues in core modules.

## Findings (Ordered by Severity)

### P0 - Missing service boundary for production API
- Evidence: `apps/api-go/cmd/invoicer/main.go` implements only `/healthz`.
- Impact:
  - No invoice read/write/query API for product consumption.
  - No external integration surface for a SaaS control plane.

### P0 - Critical domain logic concentrated in very large script modules
- Evidence:
  - `apps/workers-py/src/invplatform/cli/invoices_report.py`
  - `apps/workers-py/src/invplatform/cli/gmail_invoice_finder.py`
  - `apps/workers-py/src/invplatform/cli/graph_invoice_finder.py`
- Impact:
  - High change risk and regression probability.
  - Hard to isolate tenant-specific behavior, retries, and observability.
  - Limited reuse for API/worker split.

### P0 - Intended application-layer abstraction is still a placeholder
- Evidence: `apps/workers-py/src/invplatform/usecases/fetch_invoices.py:17-19` returns `[]`.
- Impact:
  - No true use-case layer for adapters/providers.
  - Domain logic remains coupled to CLI orchestration.

### P1 - OpenAPI contract and implementation are materially misaligned
- Evidence:
  - Contract: `integrations/openapi/invoices.yaml` defines invoice CRUD paths.
  - Runtime: `apps/api-go/cmd/invoicer/main.go` has no corresponding handlers.
- Impact:
  - Integration expectations mismatch actual behavior.
  - Blocks frontend/client generation and API-driven roadmap.

### P1 - Documented architecture/onboarding are empty
- Evidence:
  - `docs/ARCHITECTURE.md` (0 lines)
  - `docs/ONBOARDING.md` (0 lines)
  - `docs/CONTRIBUTING.md` (0 lines)
  - `apps/workers-py/README.md` (0 lines)
- Impact:
  - Single-maintainer knowledge silo risk.
  - Slower onboarding and inconsistent engineering practices.

### P1 - CI quality gates are weak/unsafe
- Evidence: `.github/workflows/ci.yml`
  - `uv pip install ... || true` (dependency failures ignored)
  - `ruff check --fix .` runs mutation during CI
  - Main root test suite is not the default CI test surface
- Impact:
  - False green pipelines.
  - Non-deterministic behavior and missed regressions.

### P1 - Dependency management is fragmented and inconsistent
- Evidence:
  - Root `requirements.txt` and `apps/workers-py/requirements.txt` differ significantly.
  - `apps/workers-py/pyproject.toml` has a third dependency list.
- Impact:
  - Drift between local/CI/runtime environments.
  - Harder reproducibility and security patching.

### P2 - Dead/unreachable code in parsing logic
- Evidence: `apps/workers-py/src/invplatform/cli/invoices_report.py:373` returns, yet logic continues at lines `374+`.
- Impact:
  - Confusing maintenance surface.
  - Signals insufficient refactor hygiene in high-risk parser code.

### P2 - Throughput ceilings embedded in provider fetch
- Evidence:
  - `apps/workers-py/src/invplatform/cli/graph_invoice_finder.py:449-471` limits to 50 pages * 50 top.
  - `...:481-484` attachment list fetch is single page (`$top=50`) with no pagination loop.
- Impact:
  - Larger inboxes may silently under-process data.

### P2 - Minor defect in Make defaults
- Evidence: `Makefile:59` output filename typo (`vrejected_outlook.json`).
- Impact:
  - Operational friction and inconsistent report naming.

## Recommended Improvement Plan

## 0-30 Days (Stabilize)
- Extract shared message/PDF processing primitives from Gmail/Graph CLIs into `invplatform/usecases/`.
- Replace placeholder `fetch_invoices()` with real orchestration contracts.
- Fix CI:
  - Remove `|| true` on dependency install.
  - Run read-only lint (`ruff check`) and fail on issues.
  - Run root `tests/` suite in CI.
- Consolidate dependency strategy to one source-of-truth (`pyproject.toml` + lock).
- Clean dead code and high-noise typing errors in core modules.

## 31-90 Days (Modularize)
- Split parser into vendor strategy plugins:
  - `parsers/base.py`, `parsers/municipal.py`, `parsers/partner.py`, etc.
- Introduce a persistence layer (Postgres models + repository pattern).
- Add idempotency keys for fetch/download/parse stages.
- Add structured logging + trace IDs across monthly workflow stages.

## 90+ Days (Platformize)
- Implement real API layer in Go (invoice query + tenant management).
- Shift monthly runner to queue-driven jobs (RabbitMQ already present).
- Introduce tenant-aware storage model and audit log pipeline.
