# Onboarding (SaaS Conversion Track)

## Purpose

This onboarding guide is for contributors working on the SaaS conversion of the invoices platform.

## Current State

- Production-grade parser/reporting domain logic exists in `apps/workers-py/src/invplatform/usecases`.
- CLI workflows are stable and must remain backward compatible.
- SaaS API layer is being introduced incrementally.

## Week 1 Deliverables

- PRD v1: `docs/PRD_V1_SAAS.md`
- HLD: `docs/ARCHITECTURE.md`
- ADRs: `docs/ADR/0001-0004`
- API contract skeleton: `integrations/openapi/invoices.yaml`

## Local Setup

1. Create environment and install deps:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -U pip`
   - `pip install -r requirements.txt`
   - `pip install -e apps/workers-py`

2. Run tests:
   - `make test`

3. Run report CLI sanity check:
   - `PYTHONPATH=apps/workers-py/src python -m invplatform.cli.invoices_report --help`

## Working Rules for SaaS Track

- Reuse usecase modules; do not duplicate parser heuristics in API handlers.
- Keep CLI outputs and behavior unchanged unless tests prove a bug fix.
- Every architecture-affecting decision must have an ADR update/addition.
- Follow `docs/ARCHITECTURE_REVIEW_POLICY.md` and fill architecture review sections in `.github/PULL_REQUEST_TEMPLATE.md`.
- Add tests for new service boundaries before integration wiring.
