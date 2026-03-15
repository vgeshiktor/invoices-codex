# Architecture Review Policy (Backend + Frontend)

Updated: 2026-03-15

## Purpose

Add focused architecture oversight without slowing down delivery.

## Roles

- Backend Architect:
  - validates data model boundaries, API contracts, tenancy isolation, queueing/runtime behavior, and backend security/performance risks.
- Frontend Architect:
  - validates app boundaries, routing/state architecture, API integration shape, responsive UX consistency, and frontend observability patterns.

## Scope Trigger

Architecture review is required when a PR changes impacted domain files:

- Backend impact examples:
  - `apps/api-go/**`
  - `apps/workers-py/**`
  - `invoices/**`
  - `integrations/**`
  - `storage/**`
  - `tests/**` (backend/runtime test changes)
- Frontend impact examples:
  - `apps/web/**`
  - `docs/frontend/**`

## PR Requirements

All PRs must include these sections:

- `## Backend Architecture Review`
- `## Frontend Architecture Review`

For an impacted domain, section must include:

- `Status: Approved`
- `Reviewed By: @<architect>`

For non-impacted domain, use:

- `Status: N/A`
- `Reviewed By: N/A`

## Merge Gates

A PR is merge-ready only when:

1. architect section for each impacted domain is marked `Approved`,
2. Sourcery/Codex review findings are resolved,
3. mergeability is clean,
4. strict validation script passes.

## Escalation Rule (KISS)

Architects may block only for `P0/P1` architecture risks:

- tenancy/safety violations
- contract-breaking changes without migration path
- major reliability/security regressions
- unbounded scaling risks

Everything else should be tracked as follow-up issues, not a merge blocker.
