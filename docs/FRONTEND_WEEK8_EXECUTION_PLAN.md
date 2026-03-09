# Frontend Week 8 Execution Plan

Date: 2026-03-09
Scope: Execute `BE-302`, `FE-503` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 8 Goal

By end of Week 8:
- scheduler runtime executes schedules at configured times.
- schedule-triggered collection runs are linked and visible in UI history.
- scheduling e2e coverage validates create/update/execution visibility.
- runtime scheduling flow is stable enough to enter observability hardening (Week 9).

## 2. Team Slots (Fill Names)

- `Owner-BE-Runtime`: backend scheduler runtime lead
- `Owner-FE-ScheduleE2E`: frontend scheduling e2e lead
- `Owner-QA`: cross-flow validation and fixture stability
- `Owner-Review`: cross-stack reviewer and merge gate

## 3. Issue Map (Week 8 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| BE-302 | Implement scheduler runtime and schedule-triggered run linkage | Owner-BE-Runtime | Owner-Review | BE-301 |
| FE-503 | Add scheduling e2e coverage | Owner-FE-ScheduleE2E | Owner-QA | FE-501 |

## 4. Backend Contract for Week 8 (Freeze Early)

Required runtime behavior:
- scheduler evaluates active schedules by timezone and `time_of_day`.
- schedule execution creates collection runs with traceable linkage to schedule id.
- schedule metadata updates after execution:
  - `last_run_at`
  - `last_run_status`
  - `next_run_at`

Required schedule-run linkage fields:
- `trigger_type` (`manual` | `schedule`)
- `schedule_id` (nullable)
- `triggered_at`

Recommended operational endpoint:
- `GET /v1/schedules/{schedule_id}/runs?limit=&offset=`

Security and reliability constraints:
- strict tenant isolation for schedule and run visibility.
- runtime failures are recorded with non-sensitive error details.
- duplicate runs for same schedule-time slot prevented via idempotency guard.

## 5. Day-by-Day Execution

## Day 1 (Mon): Runtime Contract + Scheduler Loop Baseline

Planned issues:
- BE-302 (start)

Tasks:
1. Freeze runtime execution and schedule-run linkage contract.
2. Implement scheduler polling/dispatch loop baseline.
3. Add guard against duplicate trigger for same schedule window.

End-of-day checkpoint:
- BE-302 PR opened with core runtime loop and tests.
- contract attached in issue comments.

## Day 2 (Tue): Run Linkage + Metadata Updates

Planned issues:
- BE-302 (continue)

Tasks:
1. Persist schedule linkage on triggered collection runs.
2. Update `last_run_at`, `last_run_status`, `next_run_at` after execution.
3. Add unit/integration tests for timezone-sensitive next-run calculation.

End-of-day checkpoint:
- BE-302 runtime flow complete in staging/dev environment.
- schedule-triggered runs visible via existing run APIs.

## Day 3 (Wed): Backend Stabilization + FE E2E Start

Planned issues:
- BE-302 (finish)
- FE-503 (start)

Tasks:
1. Finalize runtime error handling and observability-friendly status payloads.
2. Merge BE-302 after deterministic test pass.
3. Start scheduling e2e scenarios with stable fixtures/time controls.

End-of-day checkpoint:
- BE-302 merged.
- FE-503 at least 40% complete.

## Day 4 (Thu): Scheduling E2E Expansion

Planned issues:
- FE-503 (continue)

Tasks:
1. Add e2e: create schedule -> wait/trigger window -> run appears in history.
2. Add e2e: pause schedule -> no run emitted.
3. Add e2e: resume schedule -> run emission resumes.

End-of-day checkpoint:
- FE-503 tests stable locally and in CI dry run.

## Day 5 (Fri): CI Gate + Closeout

Planned issues:
- FE-503 (finish)

Tasks:
1. Finalize flaky-test mitigation for time-dependent scenarios.
2. Mark schedule runtime e2e checks required in CI.
3. Publish Week 8 status with handoff notes for Week 9 observability.

End-of-day checkpoint:
- FE-503 merged.
- Week 8 checks green and required.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: runtime/scheduler/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 8)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- API contract/docs updated where changed
- reviewed and merged

Week-level DoD:
- `BE-302`, `FE-503` both closed
- active schedule can trigger collection run with visible linkage
- scheduling e2e is required and green in CI
- no open P0/P1 runtime scheduling defects

## 8. Test Matrix (Minimum)

- Unit:
  - next-run calculation for timezone/day boundary cases
  - duplicate-trigger guard logic
- Integration:
  - schedule-triggered run linkage persistence
  - schedule metadata updates after success/failure
- E2E:
  - active schedule triggers visible run in UI history
  - paused schedule prevents triggers
  - resumed schedule resumes triggers

## 9. Risks and Fast Mitigations

- Risk: time-based tests are flaky in CI.
- Mitigation: freeze test clock and isolate scheduler cadence in test mode.

- Risk: duplicate triggers during worker lag.
- Mitigation: enforce runtime idempotency lock per schedule-time slot.

- Risk: schedule metadata lags behind run state.
- Mitigation: update schedule state in same transaction boundary where possible.

## 10. Week 8 Exit Artifacts

At week close, produce:
1. merged PR list for `BE-302`, `FE-503`.
2. CI links proving scheduling runtime checks are required and green.
3. short handoff note into Week 9 observability/traceability execution.
