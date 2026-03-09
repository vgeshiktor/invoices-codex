# Frontend Week 5 Execution Plan

Date: 2026-03-09
Scope: Execute `BE-202`, `FE-303`, `FE-304` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 5 Goal

By end of Week 5:
- collection orchestration is wired to provider executors and parse pipeline.
- retry flow works end-to-end for failed collection runs.
- frontend clearly distinguishes original run and retry run results.
- e2e coverage validates happy path and representative failure/retry path.

## 2. Team Slots (Fill Names)

- `Owner-BE-Orchestration`: backend collection orchestration lead
- `Owner-FE-Retry`: frontend retry UX lead
- `Owner-QA`: e2e/integration test lead
- `Owner-Review`: cross-stack reviewer and merge gate

## 3. Issue Map (Week 5 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| BE-202 | Wire collection jobs to provider executors and parse pipeline | Owner-BE-Orchestration | Owner-Review | BE-201 |
| FE-303 | Add retry UX for failed collection runs | Owner-FE-Retry | Owner-QA | BE-202 |
| FE-304 | Add collection journey e2e coverage (happy + failure) | Owner-QA | Owner-FE-Retry | FE-301 |

## 4. Backend Contract for Week 5 (Freeze Early)

Required behavior updates:
- collection job execution produces:
  - discovered/downloaded file counters
  - linked parse job ids
  - normalized failure details
- retry semantics:
  - retry is idempotency-safe
  - retry returns new run id or deterministic reused run id (must be explicit)
  - parent/child retry linkage is queryable

Recommended API additions:
- `POST /v1/collection-jobs/{collection_job_id}/retry`
- optional `GET /v1/collection-jobs/{collection_job_id}/events`

Required response fields for retries:
- `retry_of_collection_job_id` (nullable)
- `latest_retry_collection_job_id` (nullable)
- `retry_count`

Security constraints:
- tenant isolation enforced for retry and orchestration endpoints.
- failures never leak provider secrets or token materials.
- retry and orchestration transitions emit audit events with request id.

## 5. Day-by-Day Execution

## Day 1 (Mon): Orchestration Contract + Backend Execution Wiring

Planned issues:
- BE-202 (start)

Tasks:
1. Freeze orchestration and retry response contract.
2. Wire collection execution to provider runners and parse job creation.
3. Persist execution counters and parse links on collection job rows.

End-of-day checkpoint:
- BE-202 PR open with baseline orchestration tests.
- contract attached in issue comments.

## Day 2 (Tue): Backend Retry Endpoint + Failure Model

Planned issues:
- BE-202 (finish)
- FE-303 (start)

Tasks:
1. Implement retry endpoint and parent/child linkage fields.
2. Normalize provider/parse errors into UI-safe error model.
3. Start retry action in frontend run detail page.

End-of-day checkpoint:
- BE-202 merged.
- FE-303 at least 50% complete.

## Day 3 (Wed): Frontend Retry UX Completion

Planned issues:
- FE-303 (finish)

Tasks:
1. Complete retry trigger and status feedback UX.
2. Show relationship between original run and retry run.
3. Add guards to prevent duplicate user-triggered retries while request is in-flight.

End-of-day checkpoint:
- FE-303 merged.
- retry can be triggered and observed from UI without manual API calls.

## Day 4 (Thu): Test Expansion (Happy + Failure + Retry)

Planned issues:
- FE-304 (start)

Tasks:
1. Add integration tests for retry path and error rendering.
2. Add e2e: successful run, failed run, retry success path.
3. Stabilize test fixtures and deterministic failure simulation.

End-of-day checkpoint:
- FE-304 in review with stable local runs.

## Day 5 (Fri): CI Hardening + Closeout

Planned issues:
- FE-304 (finish)

Tasks:
1. Finalize flaky test mitigation and CI retries policy (if needed).
2. Ensure collection journey suite is required in CI.
3. Publish Week 5 status and readiness notes for Week 6 reporting UX.

End-of-day checkpoint:
- FE-304 merged.
- Week 5 checks green and required.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: orchestration/retry/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 5)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- API contract/docs updated where changed
- reviewed and merged

Week-level DoD:
- `BE-202`, `FE-303`, `FE-304` all closed
- failed run can be retried from UI with traceable status
- collection journey e2e (happy + failure + retry) is required and green
- no open P0/P1 retry/orchestration defects

## 8. Test Matrix (Minimum)

- Unit:
  - retry button state machine (idle/loading/success/error)
  - run relation rendering (original vs retry)
- Integration:
  - retry endpoint success/failure mapping
  - error model rendering with actionable messages
- E2E:
  - failed run -> retry -> succeeded path
  - retry attempt blocked during in-flight request
  - parse linkage appears after successful retry

## 9. Risks and Fast Mitigations

- Risk: orchestration side effects produce non-deterministic tests.
- Mitigation: use deterministic provider stubs and fixed fixtures in CI.

- Risk: duplicate retries create noisy job chains.
- Mitigation: enforce idempotency key on retry endpoint and disable repeated UI triggers.

- Risk: error payloads are too low-level for users.
- Mitigation: map backend error codes to user-safe messages with support hint + request id.

## 10. Week 5 Exit Artifacts

At week close, produce:
1. merged PR list for `BE-202`, `FE-303`, `FE-304`.
2. CI links proving collection retry suite is required and green.
3. short note of outstanding collection gaps before Week 6 report UX work.
