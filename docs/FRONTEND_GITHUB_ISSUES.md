# Frontend GitHub Issue Pack (Prefilled)

Date: 2026-03-09

Source of truth:
- `docs/FRONTEND_CONVERSION_BACKLOG.md`

How to use:
1. Create a new GitHub issue.
2. Copy one issue block from this file.
3. Keep the ID in the title (`[FE-xxx]` or `[BE-xxx]`).
4. Set labels and milestone as listed.

## E1 Frontend Foundation

### FE-001
Title: `[FE-001] Scaffold apps/web workspace with Vite + TypeScript`
Labels: `frontend`, `epic:E1`, `type:feature`, `priority:P1`
Milestone: `Week 1`
Depends on: `none`
Acceptance Criteria: `apps/web` exists; `dev/build/test` scripts run successfully in CI.

### FE-002
Title: `[FE-002] Add frontend quality gates (ESLint, Prettier, TS strict)`
Labels: `frontend`, `epic:E1`, `type:chore`, `priority:P1`
Milestone: `Week 1`
Depends on: `FE-001`
Acceptance Criteria: lint/type checks are required and fail CI on violations.

### FE-003
Title: `[FE-003] Implement app shell and protected route skeleton`
Labels: `frontend`, `epic:E1`, `type:feature`, `priority:P1`
Milestone: `Week 1`
Depends on: `FE-001`
Acceptance Criteria: app layout + navigation implemented; protected routes blocked without auth.

### FE-004
Title: `[FE-004] Generate typed API client from OpenAPI contract`
Labels: `frontend`, `epic:E1`, `type:feature`, `priority:P1`
Milestone: `Week 1`
Depends on: `FE-001`
Acceptance Criteria: generated client compiles and is used by at least one page.

### FE-005
Title: `[FE-005] Add global error boundary and fallback UX`
Labels: `frontend`, `epic:E1`, `type:feature`, `priority:P2`
Milestone: `Week 1`
Depends on: `FE-003`
Acceptance Criteria: uncaught UI errors render a safe fallback screen with retry action.

### FE-006
Title: `[FE-006] Add design tokens and baseline component styles`
Labels: `frontend`, `epic:E1`, `type:feature`, `priority:P2`
Milestone: `Week 1`
Depends on: `FE-003`
Acceptance Criteria: tokenized color/spacing/type scale is defined and used in base components.

### FE-007
Title: `[FE-007] Add frontend build/test steps to CI pipeline`
Labels: `frontend`, `epic:E1`, `type:chore`, `priority:P1`
Milestone: `Week 1`
Depends on: `FE-002`
Acceptance Criteria: CI runs frontend lint/type/test/build and blocks PR on failures.

## E2 Auth and Tenant User Model

### BE-001
Title: `[BE-001] Implement user/session auth endpoints for tenant login`
Labels: `backend`, `epic:E2`, `type:feature`, `priority:P0`
Milestone: `Week 2`
Depends on: `none`
Acceptance Criteria: `/auth/*` and `/v1/me` endpoints are available with tenant-safe session handling.

### FE-101
Title: `[FE-101] Build login/logout UI and protected-route flow`
Labels: `frontend`, `epic:E2`, `type:feature`, `priority:P0`
Milestone: `Week 2`
Depends on: `BE-001`
Acceptance Criteria: user can login/logout; protected screens require session.

### FE-102
Title: `[FE-102] Implement role-aware navigation and action-level RBAC UX`
Labels: `frontend`, `epic:E2`, `type:feature`, `priority:P1`
Milestone: `Week 2`
Depends on: `FE-101`
Acceptance Criteria: restricted actions are hidden or disabled according to role.

### FE-103
Title: `[FE-103] Implement secure session storage and renew flow`
Labels: `frontend`, `epic:E2`, `type:feature`, `priority:P1`
Milestone: `Week 2`
Depends on: `FE-101`
Acceptance Criteria: session survives refresh and handles expiration gracefully.

### FE-104
Title: `[FE-104] Add auth unit/integration/e2e test coverage`
Labels: `frontend`, `epic:E2`, `type:test`, `priority:P1`
Milestone: `Week 2`
Depends on: `FE-101`
Acceptance Criteria: login journey passes in CI with stable e2e tests.

## E3 Provider Configuration (Gmail/Outlook)

### BE-101
Title: `[BE-101] Add provider configuration domain and tenant-scoped CRUD APIs`
Labels: `backend`, `epic:E3`, `type:feature`, `priority:P0`
Milestone: `Week 3`
Depends on: `BE-001`
Acceptance Criteria: provider configs persist per tenant and are queryable safely.

### BE-102
Title: `[BE-102] Implement provider OAuth lifecycle endpoints`
Labels: `backend`, `epic:E3`, `type:feature`, `priority:P0`
Milestone: `Week 3`
Depends on: `BE-101`
Acceptance Criteria: OAuth start/callback/refresh/revoke supported for Gmail and Outlook.

### FE-201
Title: `[FE-201] Build provider settings screen (connect/disconnect/re-auth)`
Labels: `frontend`, `epic:E3`, `type:feature`, `priority:P0`
Milestone: `Week 3`
Depends on: `BE-102`
Acceptance Criteria: user can connect and manage provider state from UI.

### FE-202
Title: `[FE-202] Show provider health and sync metadata`
Labels: `frontend`, `epic:E3`, `type:feature`, `priority:P1`
Milestone: `Week 3`
Depends on: `BE-102`
Acceptance Criteria: token health and last sync status are visible on settings page.

### FE-203
Title: `[FE-203] Add provider flow tests for Gmail and Outlook`
Labels: `frontend`, `epic:E3`, `type:test`, `priority:P1`
Milestone: `Week 3`
Depends on: `FE-201`
Acceptance Criteria: e2e tests cover connect/disconnect/re-auth for both providers.

## E4 Invoice Collection Runs

### BE-201
Title: `[BE-201] Add collection_jobs model and APIs`
Labels: `backend`, `epic:E4`, `type:feature`, `priority:P0`
Milestone: `Week 4`
Depends on: `BE-102`
Acceptance Criteria: collection run lifecycle (`queued/running/succeeded/failed`) is persisted and queryable.

### BE-202
Title: `[BE-202] Wire collection jobs to provider executors and parse pipeline`
Labels: `backend`, `epic:E4`, `type:feature`, `priority:P0`
Milestone: `Week 5`
Depends on: `BE-201`
Acceptance Criteria: collection run produces files and parse job links with failure details.

### FE-301
Title: `[FE-301] Build "Collect current month" wizard with provider selector`
Labels: `frontend`, `epic:E4`, `type:feature`, `priority:P0`
Milestone: `Week 4`
Depends on: `BE-201`
Acceptance Criteria: run can be started in <=3 clicks and shows initial run id/status.

### FE-302
Title: `[FE-302] Build collection run detail/progress page`
Labels: `frontend`, `epic:E4`, `type:feature`, `priority:P1`
Milestone: `Week 4`
Depends on: `FE-301`
Acceptance Criteria: live status, file counts, and errors are visible until completion.

### FE-303
Title: `[FE-303] Add retry UX for failed collection runs`
Labels: `frontend`, `epic:E4`, `type:feature`, `priority:P1`
Milestone: `Week 5`
Depends on: `BE-202`
Acceptance Criteria: retry action works with idempotency-safe behavior and clear status feedback.

### FE-304
Title: `[FE-304] Add collection journey e2e coverage (happy + failure)`
Labels: `frontend`, `epic:E4`, `type:test`, `priority:P1`
Milestone: `Week 5`
Depends on: `FE-301`
Acceptance Criteria: CI validates successful run and representative failure scenario.

## E5 Reports and Financial Summary UX

### FE-401
Title: `[FE-401] Build report creation flow with output format selection`
Labels: `frontend`, `epic:E5`, `type:feature`, `priority:P1`
Milestone: `Week 6`
Depends on: `existing report APIs`
Acceptance Criteria: user can request report with selected formats and filters.

### FE-402
Title: `[FE-402] Build report list/detail views with status tracking`
Labels: `frontend`, `epic:E5`, `type:feature`, `priority:P1`
Milestone: `Week 6`
Depends on: `FE-401`
Acceptance Criteria: list/detail views show accurate report status transitions.

### FE-403
Title: `[FE-403] Add report artifact download actions`
Labels: `frontend`, `epic:E5`, `type:feature`, `priority:P1`
Milestone: `Week 6`
Depends on: `FE-402`
Acceptance Criteria: JSON/CSV/SUMMARY/PDF downloads work for available artifacts.

### FE-404
Title: `[FE-404] Render totals/VAT summary cards in report UX`
Labels: `frontend`, `epic:E5`, `type:feature`, `priority:P2`
Milestone: `Week 6`
Depends on: `FE-402`
Acceptance Criteria: totals and VAT shown in UI match backend report data.

### FE-405
Title: `[FE-405] Add report journey integration + e2e tests`
Labels: `frontend`, `epic:E5`, `type:test`, `priority:P1`
Milestone: `Week 6`
Depends on: `FE-401`
Acceptance Criteria: report create->status->download flow is green in CI.

## E6 Scheduling (Daily Runs)

### BE-301
Title: `[BE-301] Add schedule model and tenant-scoped schedule CRUD APIs`
Labels: `backend`, `epic:E6`, `type:feature`, `priority:P0`
Milestone: `Week 7`
Depends on: `BE-201`
Acceptance Criteria: schedules persist with timezone and pause/resume support.

### BE-302
Title: `[BE-302] Implement scheduler runtime and schedule-triggered run linkage`
Labels: `backend`, `epic:E6`, `type:feature`, `priority:P0`
Milestone: `Week 8`
Depends on: `BE-301`
Acceptance Criteria: scheduled execution creates traceable collection runs at configured time.

### FE-501
Title: `[FE-501] Build schedule create/edit/pause/resume UI`
Labels: `frontend`, `epic:E6`, `type:feature`, `priority:P1`
Milestone: `Week 7`
Depends on: `BE-301`
Acceptance Criteria: user can fully manage daily schedules from UI.

### FE-502
Title: `[FE-502] Build schedule history and next-run visibility UX`
Labels: `frontend`, `epic:E6`, `type:feature`, `priority:P1`
Milestone: `Week 7`
Depends on: `FE-501`
Acceptance Criteria: last run, next run, and recent statuses are visible.

### FE-503
Title: `[FE-503] Add scheduling e2e coverage`
Labels: `frontend`, `epic:E6`, `type:test`, `priority:P1`
Milestone: `Week 8`
Depends on: `FE-501`
Acceptance Criteria: schedule create/update and run visibility flow passes in CI.

## E7 Observability and Traceability

### BE-401
Title: `[BE-401] Add tenant-scoped audit event query API`
Labels: `backend`, `epic:E7`, `type:feature`, `priority:P0`
Milestone: `Week 9`
Depends on: `existing audit writes`
Acceptance Criteria: audit events can be listed/filtered per tenant for UI timeline use.

### FE-601
Title: `[FE-601] Define and document frontend telemetry event taxonomy`
Labels: `frontend`, `epic:E7`, `type:chore`, `priority:P1`
Milestone: `Week 9`
Depends on: `FE-001`
Acceptance Criteria: versioned event dictionary approved and referenced in implementation.

### FE-602
Title: `[FE-602] Add frontend OTel + Sentry instrumentation`
Labels: `frontend`, `epic:E7`, `type:feature`, `priority:P1`
Milestone: `Week 9`
Depends on: `FE-601`
Acceptance Criteria: key interactions produce traces; runtime errors captured with context.

### FE-603
Title: `[FE-603] Propagate and display request correlation IDs`
Labels: `frontend`, `epic:E7`, `type:feature`, `priority:P1`
Milestone: `Week 9`
Depends on: `FE-301`
Acceptance Criteria: `X-Request-ID` surfaced in key flows and copyable for support.

### FE-604
Title: `[FE-604] Build tenant activity timeline UI from audit events`
Labels: `frontend`, `epic:E7`, `type:feature`, `priority:P1`
Milestone: `Week 9`
Depends on: `BE-401`
Acceptance Criteria: users can filter and inspect chronological audit events.

### FE-605
Title: `[FE-605] Add support bundle export for failed run diagnostics`
Labels: `frontend`, `epic:E7`, `type:feature`, `priority:P2`
Milestone: `Week 9`
Depends on: `FE-603`
Acceptance Criteria: support bundle export includes relevant request IDs and status context.

## E8 Quality, Accessibility, and Release

### BE-402
Title: `[BE-402] Centralize workers-py test import path setup in shared conftest`
Labels: `backend`, `epic:E8`, `type:chore`, `priority:P2`
Milestone: `Week 10`
Depends on: `none`
Acceptance Criteria: test bootstrap path setup is centralized; duplicated per-file `sys.path` setup is removed from touched suites; coverage gate remains green.
GitHub Issue: `#51` (`https://github.com/vgeshiktor/invoices-codex/issues/51`)

### FE-701
Title: `[FE-701] Enforce frontend testing pyramid in CI`
Labels: `frontend`, `epic:E8`, `type:chore`, `priority:P1`
Milestone: `Week 10`
Depends on: `FE-001`
Acceptance Criteria: unit/integration/e2e suites all run and are required checks.

### FE-702
Title: `[FE-702] Enforce >=80% frontend coverage gate`
Labels: `frontend`, `epic:E8`, `type:chore`, `priority:P1`
Milestone: `Week 10`
Depends on: `FE-701`
Acceptance Criteria: CI blocks merges below 80% frontend coverage.

### FE-703
Title: `[FE-703] Add accessibility quality gate (automation + checklist)`
Labels: `frontend`, `epic:E8`, `type:quality`, `priority:P1`
Milestone: `Week 10`
Depends on: `FE-003`
Acceptance Criteria: no P1/P2 a11y violations on critical journeys.

### FE-704
Title: `[FE-704] Add Lighthouse mobile performance budgets`
Labels: `frontend`, `epic:E8`, `type:quality`, `priority:P1`
Milestone: `Week 10`
Depends on: `FE-003`
Acceptance Criteria: performance budgets are defined and enforced on key routes.

### FE-705
Title: `[FE-705] Create release readiness checklist and rollback runbook`
Labels: `frontend`, `epic:E8`, `type:chore`, `priority:P1`
Milestone: `Week 10`
Depends on: `FE-701`
Acceptance Criteria: release checklist and rollback procedure exist and are reviewed.
