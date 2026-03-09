# Frontend Week 6 Execution Plan

Date: 2026-03-09
Scope: Execute `FE-401..FE-405` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 6 Goal

By end of Week 6:
- report creation flow is available in UI.
- report list/detail screens show accurate status transitions.
- artifact downloads work for JSON/CSV/SUMMARY/PDF.
- totals/VAT summary cards are visible and validated against backend response.
- report journey test coverage (integration + e2e) is in CI.

## 2. Team Slots (Fill Names)

- `Owner-FE-Reports`: report builder/list/detail lead
- `Owner-FE-Downloads`: artifact download and totals cards lead
- `Owner-QA`: report journey test automation lead
- `Owner-Review`: frontend review and merge gate

## 3. Issue Map (Week 6 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| FE-401 | Build report creation flow with output format selection | Owner-FE-Reports | Owner-FE-Downloads | existing report APIs |
| FE-402 | Build report list/detail views with status tracking | Owner-FE-Reports | Owner-QA | FE-401 |
| FE-403 | Add report artifact download actions | Owner-FE-Downloads | Owner-FE-Reports | FE-402 |
| FE-404 | Render totals/VAT summary cards in report UX | Owner-FE-Downloads | Owner-QA | FE-402 |
| FE-405 | Add report journey integration + e2e tests | Owner-QA | Owner-FE-Reports | FE-401 |

## 4. Contract Check for Week 6 (Freeze Early)

Use existing endpoints:
- `POST /v1/reports`
- `GET /v1/reports`
- `GET /v1/reports/{report_id}`
- `GET /v1/reports/{report_id}/download?format=...`
- `POST /v1/reports/{report_id}/retry`

Required frontend assumptions to freeze:
- status values: `queued`, `running`, `succeeded`, `failed`
- artifact formats: `json`, `csv`, `summary_csv`, `pdf`
- retry action available only for `failed` reports
- empty artifact list handled gracefully

## 5. Day-by-Day Execution

## Day 1 (Mon): Report Builder Baseline

Planned issues:
- FE-401 (start)

Tasks:
1. Implement report builder form with format selection.
2. Add parse job scope/filter inputs based on current API.
3. Submit report requests and render immediate acknowledgement.

End-of-day checkpoint:
- FE-401 PR opened.
- create-report happy path works locally.

## Day 2 (Tue): Report Builder Completion + List View Start

Planned issues:
- FE-401 (finish)
- FE-402 (start)

Tasks:
1. Finalize create-flow validation and error states.
2. Build reports list with status badges and sorting.
3. Add route to report detail page.

End-of-day checkpoint:
- FE-401 merged.
- FE-402 at least 50% complete.

## Day 3 (Wed): Report Detail + Status Tracking

Planned issues:
- FE-402 (finish)
- FE-403 (start)

Tasks:
1. Complete report detail screen with artifacts section.
2. Add refresh/poll strategy for status transitions.
3. Implement artifact download actions for available formats.

End-of-day checkpoint:
- FE-402 merged.
- FE-403 in progress with at least one format download working.

## Day 4 (Thu): Downloads Completion + Totals/VAT Cards

Planned issues:
- FE-403 (finish)
- FE-404

Tasks:
1. Complete downloads for JSON/CSV/SUMMARY/PDF.
2. Add totals and VAT cards using report/invoice summary data.
3. Verify responsive rendering for reports list/detail on mobile and desktop.

End-of-day checkpoint:
- FE-403 and FE-404 merged.
- totals/VAT values match backend data for test fixtures.

## Day 5 (Fri): Full Report Journey Test Coverage

Planned issues:
- FE-405

Tasks:
1. Add integration tests for create/list/detail/download flows.
2. Add e2e for report create -> status -> download.
3. Stabilize flaky cases and mark report journey checks as required in CI.

End-of-day checkpoint:
- FE-405 merged.
- Week 6 report journey checks green and required.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: report/api/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 6)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- docs updated if report UX contract changed
- reviewed and merged

Week-level DoD:
- `FE-401`, `FE-402`, `FE-403`, `FE-404`, `FE-405` all closed
- report journey is fully usable from UI
- report journey checks are required and green in CI
- no open P0/P1 report UX defects

## 8. Test Matrix (Minimum)

- Unit:
  - report form validation and format selection logic
  - status badge/state mapping
  - totals/VAT card calculations and formatting
- Integration:
  - create/list/detail API mapping
  - artifact download action behavior
  - retry action visibility for failed reports
- E2E:
  - create report -> queued/running/succeeded
  - open report detail -> download artifact
  - failed report -> retry action visible and functioning

## 9. Risks and Fast Mitigations

- Risk: status polling creates noisy traffic.
- Mitigation: apply backoff and stop polling on terminal states.

- Risk: report totals interpretation differs by backend payload.
- Mitigation: lock fixture-based validation and document mapping explicitly.

- Risk: PDF download handling varies by browser.
- Mitigation: test both direct download and new-tab fallback behavior.

## 10. Week 6 Exit Artifacts

At week close, produce:
1. merged PR list for `FE-401..FE-405`.
2. CI links proving report journey checks are required and green.
3. short note documenting handoff into Week 7 scheduling work.
