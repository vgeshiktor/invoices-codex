# PR Validation Report

Date: 2026-03-15
PR: https://github.com/vgeshiktor/invoices-codex/pull/73
Repository: vgeshiktor/invoices-codex

## Inputs
- PR Number: 73
- Base/Head: codex/andromeda-fe-403 <- codex/nebula-fe-404
- Expected issues: vgeshiktor/invoices-codex#27
- Design docs: docs/FRONTEND_CONVERSION_BACKLOG.md,docs/FRONTEND_WEEK6_EXECUTION_PLAN.md,docs/STAKEHOLDER_DEMO_RUNBOOK.md,docs/ARCHITECTURE.md
- Traceability rules: docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json

## A) PR Governance Checklist (14 Gates)

| # | Validation Item | Status | Evidence |
|---|---|---|---|
| 1 | PR title format matches team convention | PASS | Title: [FE-404] Render totals/VAT summary cards in report UX |
| 2 | PR summary follows documentation guidelines | PASS | Required sections found: problem, design, testing, rollout/risk. |
| 3 | Commit messages follow naming convention | PASS | All commit headlines match convention. |
| 4 | Reviewer guide exists and is actionable | PASS | Reviewer guide section found. |
| 5 | File-level changes are scoped/aligned | PASS | Changed files: 5. Top files: apps/web/src/App.css (+28/-0);apps/web/src/features/reports/components/ReportDetailScreen.integration.test.tsx (+1/-0);apps/web/src/features/reports/components/ReportDetailScreen.tsx (+48/-19);apps/web/src/features/reports/components/ReportSummaryCards.integration.test.tsx (+44/-0);apps/web/src/features/reports/components/ReportSummaryCards.tsx (+183/-0) |
| 6 | Linked issues are correct | PASS | No unexpected linked issues. |
| 7 | Linked issues are complete | FAIL | Missing expected linked issues: vgeshiktor/invoices-codex#27 |
| 8 | Sourcery review findings resolved | N/A | No Sourcery review threads found. |
| 9 | Codex review findings resolved | N/A | No Codex review threads found. |
| 10 | PR summary lists resolved issues with closing keywords | FAIL | No closing issue references found in PR metadata. |
| 11 | Closing keyword exists in PR body or commits | PASS | Closing keyword reference found in PR body/commits. |
| 12 | Cross-repo issues use full form when needed | N/A | No cross-repo linked issues. |
| 13 | All checks are green | FAIL | Failing/non-success checks: Sourcery review: COMPLETED/SKIPPED |
| 14 | No conflicts with base branch | PASS | mergeable=MERGEABLE, mergeStateStatus=CLEAN |

## B) PR Body Content Requirements

- Status: PASS
- Evidence: All required PR body sections found.

## C) Design/Contract Traceability Matrix

| Requirement Source | Requirement | Status | Evidence in PR | Notes |
|---|---|---|---|---|
| docs/FRONTEND_GITHUB_ISSUES.md | FE-404 adds totals and VAT summary cards to report UX | PASS | Matched pattern: ReportSummaryCards |  |
| docs/FRONTEND_WEEK6_EXECUTION_PLAN.md | FE-404 derives totals from backend report data | PASS | Matched pattern: downloadReportArtifact |  |
| docs/FRONTEND_WEEK6_EXECUTION_PLAN.md | FE-404 includes totals/VAT integration coverage | PASS | Matched pattern: ReportSummaryCards.integration.test.tsx |  |

## D) Linked Issue Validation

### Expected Issues from Scope
- vgeshiktor/invoices-codex#27

### Found in PR (Closing References)
- (none)

## E) Review Findings Closure

### Sourcery
- Total threads: 0
- Open threads: 0
- Status: N/A

### Codex
- Total threads: 0
- Open threads: 0
- Status: N/A

## F) CI and Mergeability

- Status checks: 16
- Checks gate: FAIL (Failing/non-success checks: Sourcery review: COMPLETED/SKIPPED)
- Mergeability gate: PASS (mergeable=MERGEABLE, mergeStateStatus=CLEAN)

## G) Final Verdict

- Overall: FAIL
- Governance gates: 8 passed, 3 failed, 3 n/a (out of 14)
- Content completeness: PASS
- Design traceability fails: 0
- Design traceability deferred/partial: 0
- Decision: Not ready to merge
