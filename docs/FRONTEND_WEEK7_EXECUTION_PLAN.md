# Frontend Week 7 Execution Plan

Date: 2026-03-09
Scope: Execute `BE-301`, `FE-501`, `FE-502` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 7 Goal

By end of Week 7:
- schedule domain and tenant-scoped schedule CRUD APIs exist.
- frontend supports creating, editing, pausing, and resuming daily schedules.
- schedule history view shows next run, last run, and recent run statuses.
- scheduling UX is responsive and usable on mobile and desktop.

## 2. Team Slots (Fill Names)

- `Owner-BE-Schedule`: backend schedule model/API lead
- `Owner-FE-Schedule`: frontend schedule management lead
- `Owner-FE-History`: frontend schedule history/visibility lead
- `Owner-QA`: scheduling test and validation lead
- `Owner-Review`: cross-stack reviewer and merge gate

## 3. Issue Map (Week 7 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| BE-301 | Add schedule model and tenant-scoped schedule CRUD APIs | Owner-BE-Schedule | Owner-Review | BE-201 |
| FE-501 | Build schedule create/edit/pause/resume UI | Owner-FE-Schedule | Owner-FE-History | BE-301 |
| FE-502 | Build schedule history and next-run visibility UX | Owner-FE-History | Owner-FE-Schedule | FE-501 |

## 4. Backend Contract for Week 7 (Freeze Early)

Schedule endpoints (tenant-scoped):
- `POST /v1/schedules`
- `GET /v1/schedules`
- `GET /v1/schedules/{schedule_id}`
- `PATCH /v1/schedules/{schedule_id}`
- `POST /v1/schedules/{schedule_id}/pause`
- `POST /v1/schedules/{schedule_id}/resume`

Required schedule fields:
- `id`
- `tenant_id`
- `status` (`active` | `paused`)
- `frequency` (`daily`)
- `time_of_day` (HH:MM)
- `timezone`
- `providers` (gmail/outlook selection)
- `next_run_at`
- `last_run_at` (nullable)
- `last_run_status` (nullable)

Security constraints:
- strict tenant isolation on all schedule operations.
- schedule updates produce audit events with request id.
- invalid timezone/time values return `400` with explicit error details.

## 5. Day-by-Day Execution

## Day 1 (Mon): Contract Freeze + Backend Model

Planned issues:
- BE-301 (start)

Tasks:
1. Freeze schedule request/response contract and validation rules.
2. Add schedule model/migration with timezone and provider fields.
3. Implement `POST` and `GET list` endpoints with tenant-scoped tests.

End-of-day checkpoint:
- BE-301 PR opened with create/list baseline.
- contract attached in issue comments.

## Day 2 (Tue): Backend CRUD Completion + FE Schedule Start

Planned issues:
- BE-301 (finish)
- FE-501 (start)

Tasks:
1. Complete `GET by id`, `PATCH`, pause/resume endpoints.
2. Add invalid timezone/time validation tests.
3. Start schedule UI form (create/edit) and action buttons (pause/resume).

End-of-day checkpoint:
- BE-301 merged.
- FE-501 at least 50% complete.

## Day 3 (Wed): Schedule UI Completion

Planned issues:
- FE-501 (finish)

Tasks:
1. Complete create/edit/pause/resume flows in UI.
2. Add state handling for active vs paused schedules.
3. Validate forms and error messages for invalid inputs.

End-of-day checkpoint:
- FE-501 merged.
- schedule management usable end-to-end.

## Day 4 (Thu): History and Visibility UX

Planned issues:
- FE-502 (start/finish)

Tasks:
1. Build schedule history view with next run and last run cards.
2. Show recent statuses for schedule-triggered runs.
3. Ensure responsive behavior for data-dense sections (table/card fallback).

End-of-day checkpoint:
- FE-502 merged.
- next-run and last-run visibility available in UI.

## Day 5 (Fri): Stabilization + Week Close

Planned issues:
- hardening tasks under FE-501/FE-502

Tasks:
1. Add integration tests for schedule CRUD and pause/resume.
2. Add e2e for create -> pause/resume -> history visibility.
3. Publish Week 7 status and handoff notes for Week 8 runtime scheduling.

End-of-day checkpoint:
- Week 7 checks green in CI.
- no open P0/P1 defects for schedule baseline UX/API.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: schedule/backend/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 7)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- API contract/docs updated where changed
- reviewed and merged

Week-level DoD:
- `BE-301`, `FE-501`, `FE-502` all closed
- schedule create/edit/pause/resume is usable in UI
- schedule history shows next/last run states
- no open P0/P1 schedule baseline defects

## 8. Test Matrix (Minimum)

- Unit:
  - schedule form validation (time/timezone/providers)
  - active/paused status rendering logic
- Integration:
  - schedule create/update/pause/resume API mapping
  - history panel data rendering for nullable fields
- E2E:
  - create daily schedule -> appears in list/history
  - pause and resume schedule from UI
  - next run and last run states visible after refresh

## 9. Risks and Fast Mitigations

- Risk: timezone handling bugs create incorrect next-run display.
- Mitigation: store UTC + timezone and test with fixed-time fixtures.

- Risk: schedule state drift between FE and BE.
- Mitigation: use explicit enum contract and strict client typing.

- Risk: history data may be incomplete before Week 8 runtime wiring.
- Mitigation: display partial states clearly and mark pending runtime linkage.

## 10. Week 7 Exit Artifacts

At week close, produce:
1. merged PR list for `BE-301`, `FE-501`, `FE-502`.
2. CI links proving schedule baseline checks are green.
3. short handoff note for Week 8 (`BE-302`, `FE-503`) runtime scheduling execution.
