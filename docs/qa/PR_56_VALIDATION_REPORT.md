# PR Validation Report

Date: 2026-03-13
PR: https://github.com/vgeshiktor/invoices-codex/pull/56
Repository: vgeshiktor/invoices-codex

## Inputs
- PR Number: 56
- Base/Head: main <- codex/orion-fe-001
- Expected issues: vgeshiktor/invoices-codex#1
- Design docs: docs/FRONTEND_WEEK1_EXECUTION_PLAN.md,docs/frontend/FE_WEEK1_BOOTSTRAP_CHECKLIST.md,docs/FRONTEND_GITHUB_ISSUES.md
- Traceability rules: (not provided)

## A) PR Governance Checklist (14 Gates)

| # | Validation Item | Status | Evidence |
|---|---|---|---|
| 1 | PR title format matches team convention | PASS | Title: [FE-001] Scaffold apps/web workspace with Vite + TypeScript |
| 2 | PR summary follows documentation guidelines | PASS | Required sections found: problem, design, testing, rollout/risk. |
| 3 | Commit messages follow naming convention | FAIL | Non-conforming commit headlines: Merge branch 'main' into codex/orion-fe-001 |
| 4 | Reviewer guide exists and is actionable | PASS | Reviewer guide section found. |
| 5 | File-level changes are scoped/aligned | PASS | Changed files: 9. Top files: apps/web/README.md (+1/-1);apps/web/package-lock.json (+3/-3);apps/web/package.json (+4/-0);apps/web/src/App.css (+41/-0);apps/web/src/App.tsx (+35/-0);apps/web/src/index.css (+53/-5);apps/web/src/lib/env.test.ts (+21/-0);apps/web/src/lib/env.ts (+11/-0);docs/qa/PR_56_VALIDATION_REPORT.md (+85/-0) |
| 6 | Linked issues are correct | PASS | No unexpected linked issues. |
| 7 | Linked issues are complete | PASS | All expected issues are linked. |
| 8 | Sourcery review findings resolved | PASS | All Sourcery threads resolved (5/5). |
| 9 | Codex review findings resolved | PASS | All Codex threads resolved (1/1). |
| 10 | PR summary lists resolved issues with closing keywords | PASS | All linked issues are listed with closing keywords in PR body. |
| 11 | Closing keyword exists in PR body or commits | PASS | Closing keyword reference found in PR body/commits. |
| 12 | Cross-repo issues use full form when needed | N/A | No cross-repo linked issues. |
| 13 | All checks are green | FAIL | Failing/non-success checks: frontend-checks: COMPLETED/FAILURE;frontend-checks: COMPLETED/FAILURE |
| 14 | No conflicts with base branch | FAIL | mergeable=MERGEABLE, mergeStateStatus=UNSTABLE |

## B) PR Body Content Requirements

- Status: PASS
- Evidence: All required PR body sections found.

## C) Design/Contract Traceability Matrix

| Requirement Source | Requirement | Status | Evidence in PR | Notes |
|---|---|---|---|---|
| docs/FRONTEND_WEEK1_EXECUTION_PLAN.md | Document-level coverage heuristic | PARTIAL | doc exists | Provide --traceability-file for requirement-level validation. |
| docs/frontend/FE_WEEK1_BOOTSTRAP_CHECKLIST.md | Document-level coverage heuristic | PARTIAL | doc exists | Provide --traceability-file for requirement-level validation. |
| docs/FRONTEND_GITHUB_ISSUES.md | Document-level coverage heuristic | PARTIAL | doc exists | Provide --traceability-file for requirement-level validation. |

## D) Linked Issue Validation

### Expected Issues from Scope
- vgeshiktor/invoices-codex#1

### Found in PR (Closing References)
- vgeshiktor/invoices-codex#1

## E) Review Findings Closure

### Sourcery
- Total threads: 5
- Open threads: 0
- Status: PASS

### Codex
- Total threads: 1
- Open threads: 0
- Status: PASS

## F) CI and Mergeability

- Status checks: 5
- Checks gate: FAIL (Failing/non-success checks: frontend-checks: COMPLETED/FAILURE;frontend-checks: COMPLETED/FAILURE)
- Mergeability gate: FAIL (mergeable=MERGEABLE, mergeStateStatus=UNSTABLE)

## G) Final Verdict

- Overall: FAIL
- Governance gates: 10 passed, 3 failed, 1 n/a (out of 14)
- Content completeness: PASS
- Design traceability fails: 0
- Design traceability deferred/partial: 3
- Decision: Not ready to merge
