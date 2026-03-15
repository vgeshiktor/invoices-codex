# Contributing Guide

## Goal

Keep delivery fast while protecting parser correctness and tenant isolation.

## Branch and PR Discipline

- Use short-lived branches from main.
- Keep PRs small and vertical (one slice per PR where possible).
- Include:
  - problem statement
  - design notes
  - backend architecture review
  - frontend architecture review
  - tests added/updated
  - rollout/risk notes

## Required Checks

- `make test`
  - includes Python coverage gate: minimum `80%` on source modules (tests excluded)
- `make lint`
- mypy on changed Python modules
- OpenAPI contract updated if endpoint behavior changes

## Architecture and ADR Policy

- If a change affects architecture, security model, tenancy, queueing, or storage, add/update an ADR under `docs/ADR/`.
- Reference ADR IDs in PR descriptions when relevant.
- Follow `docs/ARCHITECTURE_REVIEW_POLICY.md` for architect review responsibilities and merge gates.

## SaaS Safety Rules

- All tenant-owned queries must filter by `tenant_id`.
- API keys must be hashed at rest.
- Avoid introducing synchronous heavy processing in request handlers.
- Preserve existing CLI compatibility unless explicitly approved.

## Definition of Done (MVP Track)

- Acceptance criteria satisfied.
- Tests for happy path + at least one failure path.
- Observability hooks added (logs/metrics) where relevant.
- Docs updated (`PRD`, `ARCHITECTURE`, `OpenAPI`, or ADR) as needed.
