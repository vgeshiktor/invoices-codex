# Frontend Week 4 Execution Plan

Date: 2026-03-09
Scope: Execute `BE-201`, `FE-301`, `FE-302` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 4 Goal

By end of Week 4:
- collection job domain and APIs exist (`queued/running/succeeded/failed`).
- frontend includes "Collect current month" wizard.
- frontend includes collection run detail/progress page.
- end-to-end flow exists from provider selection to run status visibility.

## 2. Team Slots (Fill Names)

- `Owner-BE-Collection`: backend collection job lead
- `Owner-FE-Wizard`: frontend collection wizard lead
- `Owner-FE-RunDetail`: frontend run detail/status lead
- `Owner-QA`: collection flow validation lead
- `Owner-Review`: cross-stack reviewer and merge gate

## 3. Issue Map (Week 4 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| BE-201 | Add collection_jobs model and APIs | Owner-BE-Collection | Owner-Review | BE-102 |
| FE-301 | Build "Collect current month" wizard with provider selector | Owner-FE-Wizard | Owner-FE-RunDetail | BE-201 |
| FE-302 | Build collection run detail/progress page | Owner-FE-RunDetail | Owner-FE-Wizard | FE-301 |

## 4. Backend Contract for Week 4 (Freeze Early)

Collection job endpoints (tenant-scoped):
- `POST /v1/collection-jobs`
- `GET /v1/collection-jobs`
- `GET /v1/collection-jobs/{collection_job_id}`

Recommended response fields:
- `id`
- `tenant_id`
- `status` (`queued` | `running` | `succeeded` | `failed`)
- `providers` (selected providers for this run)
- `month_scope` (e.g., `2026-03`)
- `started_at`
- `finished_at`
- `files_discovered`
- `files_downloaded`
- `parse_job_ids` (if created)
- `error_message` (nullable)

Security constraints:
- strict tenant isolation on every query.
- idempotency support for create endpoint.
- collection lifecycle events recorded in audit trail with request id.

## 5. Day-by-Day Execution

## Day 1 (Mon): Contract Freeze + Backend Model

Planned issues:
- BE-201 (start)

Tasks:
1. Freeze collection job request/response contract.
2. Add collection job model/migration and status lifecycle.
3. Implement `POST /v1/collection-jobs` with baseline validation.

End-of-day checkpoint:
- contract frozen and attached to BE-201.
- backend PR open with create endpoint tests.

## Day 2 (Tue): Backend List/Get + FE Wizard Start

Planned issues:
- BE-201 (finish)
- FE-301 (start)

Tasks:
1. Implement `GET /v1/collection-jobs` and `GET /v1/collection-jobs/{id}`.
2. Add tenant isolation and lifecycle transition tests.
3. Build wizard first step: provider selection and month scope.

End-of-day checkpoint:
- BE-201 merged.
- FE-301 at least 50% complete.

## Day 3 (Wed): Wizard Completion

Planned issues:
- FE-301 (finish)

Tasks:
1. Complete wizard submit flow to create collection job.
2. Show immediate run acknowledgement (run id + status).
3. Add error states and retries for creation failures.

End-of-day checkpoint:
- FE-301 merged.
- user can create a collection run in <=3 clicks.

## Day 4 (Thu): Run Detail/Progress Screen

Planned issues:
- FE-302 (start/finish)

Tasks:
1. Build collection run detail page from `GET /v1/collection-jobs/{id}`.
2. Render status timeline and file counters.
3. Add polling or refresh control for live status progression.

End-of-day checkpoint:
- FE-302 merged.
- run detail screen works on mobile and desktop widths.

## Day 5 (Fri): Flow Stabilization + Closeout

Planned issues:
- hardening tasks under FE-301/FE-302

Tasks:
1. Add integration tests for wizard -> run detail navigation path.
2. Add e2e for happy path and failed run rendering.
3. Publish Week 4 status report and readiness notes for Week 5 retry/orchestration hardening.

End-of-day checkpoint:
- Week 4 checks green in CI.
- no open P0/P1 defects in collection run baseline flow.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: collection/backend/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 4)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- API contract/docs updated where changed
- reviewed and merged

Week-level DoD:
- `BE-201`, `FE-301`, `FE-302` all closed
- user can launch and monitor collection run from UI
- collection baseline e2e is required and green
- no open P0/P1 collection baseline defects

## 8. Test Matrix (Minimum)

- Unit:
  - wizard form validation and provider selection logic
  - status-to-UI badge mapping
- Integration:
  - collection job create/list/get API interactions
  - error rendering for failed create/get requests
- E2E:
  - create collection run via wizard -> open run detail
  - run status transitions visible
  - failed run surfaces actionable error

## 9. Risks and Fast Mitigations

- Risk: collection status updates are not visible quickly enough.
- Mitigation: use short-interval polling with backoff and manual refresh control.

- Risk: provider selection contract mismatch between FE and BE.
- Mitigation: freeze enum values Day 1 and validate with contract tests.

- Risk: run detail grows too complex early.
- Mitigation: keep Week 4 scope to key lifecycle and counters only; defer advanced logs to later week.

## 10. Week 4 Exit Artifacts

At week close, produce:
1. merged PR list for `BE-201`, `FE-301`, `FE-302`.
2. CI links proving collection baseline checks are required and green.
3. short note documenting open gaps for Week 5 (`BE-202`, `FE-303`, `FE-304`).
