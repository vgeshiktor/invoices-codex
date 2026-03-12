# Frontend Week 10 Execution Plan

Date: 2026-03-09
Scope: Execute `FE-701..FE-705` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 10 Goal

By end of Week 10:
- frontend test pyramid is fully enforced in CI.
- frontend coverage gate is >=80% and required.
- accessibility quality gate is active and no P1/P2 issues remain on critical flows.
- performance budgets are defined and enforced for key routes.
- release checklist and rollback runbook are finalized for go-live readiness.

## 2. Team Slots (Fill Names)

- `Owner-QA-Lead`: testing pyramid and coverage gate lead
- `Owner-FE-Quality`: accessibility/performance quality lead
- `Owner-Release`: release checklist and rollback runbook lead
- `Owner-Review`: final release gate reviewer

## 3. Issue Map (Week 10 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| FE-701 | Enforce frontend testing pyramid in CI | Owner-QA-Lead | Owner-Review | FE-001 |
| FE-702 | Enforce >=80% frontend coverage gate | Owner-QA-Lead | Owner-FE-Quality | FE-701 |
| FE-703 | Add accessibility quality gate (automation + checklist) | Owner-FE-Quality | Owner-QA-Lead | FE-003 |
| FE-704 | Add Lighthouse mobile performance budgets | Owner-FE-Quality | Owner-QA-Lead | FE-003 |
| FE-705 | Create release readiness checklist and rollback runbook | Owner-Release | Owner-Review | FE-701 |

## 4. Quality Gate Contract for Week 10 (Freeze Early)

Testing pyramid in CI:
- required suites: unit + integration + e2e
- each suite has required status checks on PRs
- FE-701 required check names:
  - `frontend / unit`
  - `frontend / integration`
  - `frontend / e2e`

Coverage contract:
- minimum frontend coverage threshold: `80%`
- threshold enforced at PR and default branch pipelines

Accessibility contract:
- automated a11y checks on critical screens/journeys
- manual checklist for keyboard navigation, focus order, contrast, semantics
- no unresolved P1/P2 a11y issues

Performance contract:
- mobile Lighthouse budgets for key pages:
  - dashboard/home
  - collection runs
  - reports list/detail
  - schedules

Release contract:
- go-live checklist with explicit owner sign-off
- rollback runbook with trigger criteria and recovery steps

## 5. Day-by-Day Execution

## Day 1 (Mon): CI Pyramid Baseline

Planned issues:
- FE-701 (start)

Tasks:
1. Ensure unit/integration/e2e suites run in CI pipeline.
2. Mark all three suites as required PR checks.
3. Document failure triage ownership and response SLA.

End-of-day checkpoint:
- FE-701 PR opened.
- CI shows all test tiers running on PR.

## Day 2 (Tue): Coverage Gate Enforcement

Planned issues:
- FE-701 (finish)
- FE-702 (start)

Tasks:
1. Finalize and merge test-pyramid enforcement.
2. Configure coverage reporting and threshold gate at 80%.
3. Add clear CI output for coverage shortfalls.

End-of-day checkpoint:
- FE-701 merged.
- FE-702 at least 50% complete.

## Day 3 (Wed): Accessibility Gate

Planned issues:
- FE-702 (finish)
- FE-703 (start/finish)

Tasks:
1. Merge coverage gate and confirm failing behavior below threshold.
2. Add automated accessibility checks for critical routes.
3. Complete manual a11y checklist and track any residual defects.

End-of-day checkpoint:
- FE-702 and FE-703 merged.
- no open P1/P2 accessibility findings.

## Day 4 (Thu): Performance Budgets

Planned issues:
- FE-704 (start/finish)

Tasks:
1. Establish Lighthouse mobile budgets for key routes.
2. Add CI perf checks and regression tolerance rules.
3. Address top bottlenecks found by baseline run.

End-of-day checkpoint:
- FE-704 merged.
- performance budgets enforced in CI.

## Day 5 (Fri): Release Readiness + Final Closeout

Planned issues:
- FE-705 (start/finish)

Tasks:
1. Finalize release readiness checklist.
2. Finalize rollback runbook with concrete rollback triggers.
3. Publish Week 10 completion report and overall 10-week readiness summary.

End-of-day checkpoint:
- FE-705 merged.
- all Week 10 quality gates green and required.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: ci/coverage/a11y/perf/release
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 10)

For each issue:
- acceptance criteria from issue body met
- tests/checks added and green in CI
- docs/runbooks updated where changed
- reviewed and merged

Week-level DoD:
- `FE-701`, `FE-702`, `FE-703`, `FE-704`, `FE-705` all closed
- all quality gates required and green
- release checklist and rollback runbook approved
- no open P0/P1 launch blockers

## 8. Test and Verification Matrix (Minimum)

- CI checks:
  - required pyramid checks:
    - `frontend / unit`
    - `frontend / integration`
    - `frontend / e2e`
  - coverage threshold >=80% enforced
  - a11y checks enforced on critical routes
  - performance budget checks enforced
- Manual verification:
  - keyboard-only walkthrough on key journeys
  - responsive smoke checks on mobile and desktop
  - rollback drill simulation against staging build

## 9. Risks and Fast Mitigations

- Risk: coverage gate causes late-week merge blockage.
- Mitigation: identify low-coverage hotspots on Day 2 and patch early.

- Risk: performance budgets fail due to third-party scripts.
- Mitigation: isolate third-party impact and set separate monitoring thresholds.

- Risk: a11y fixes spill beyond Week 10.
- Mitigation: prioritize critical journey defects first; defer non-blocking issues with owner/date.

- Risk: rollback runbook is untested.
- Mitigation: perform one staged rollback rehearsal before closeout.

## 10. Week 10 Exit Artifacts

At week close, produce:
1. merged PR list for `FE-701..FE-705`.
2. CI links proving all quality gates are required and green.
3. final go-live readiness package (checklist + rollback runbook + risk sign-off).
