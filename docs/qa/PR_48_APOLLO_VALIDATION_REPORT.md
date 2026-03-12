# PR Validation Report

Date: 2026-03-12
PR: https://github.com/vgeshiktor/invoices-codex/pull/48
Repository: vgeshiktor/invoices-codex

## Inputs
- PR Number: 48
- Base/Head: main <- codex/apollo
- Expected issues: vgeshiktor/invoices-codex#7
- Design docs: docs/qa/FE_WEEK1_CI_MATRIX.md,docs/qa/FE_TEST_HARNESS_CHECKLIST.md
- Traceability rules: (not provided)

## A) PR Governance Checklist (14 Gates)

| # | Validation Item | Status | Evidence |
|---|---|---|---|
| 1 | PR title format matches team convention | FAIL | Title does not match expected format [FE-xxx]/[BE-xxx]: docs(qa): add Week 1 FE CI matrix and test harness checklist |
| 2 | PR summary follows documentation guidelines | FAIL | Missing required sections: Problem Statement,Design Notes,Rollout/Risk Notes |
| 3 | Commit messages follow naming convention | FAIL | Non-conforming commit headlines: Update docs/qa/FE_WEEK1_CI_MATRIX.md Merge branch 'main' into codex/apollo |
| 4 | Reviewer guide exists and is actionable | FAIL | Reviewer guide section not found in PR body. |
| 5 | File-level changes are scoped/aligned | PASS | Changed files: 2. Top files: docs/qa/FE_WEEK1_CI_MATRIX.md (+1/-1);tests/test_usecases_report_totals_vendor_strategies.py (+285/-0) |
| 6 | Linked issues are correct | PASS | No unexpected linked issues. |
| 7 | Linked issues are complete | FAIL | Missing expected linked issues: vgeshiktor/invoices-codex#7 |
| 8 | Sourcery review findings resolved | PASS | All Sourcery threads resolved (2/2). |
| 9 | Codex review findings resolved | N/A | No Codex review threads found. |
| 10 | PR summary lists resolved issues with closing keywords | FAIL | No closing issue references found in PR metadata. |
| 11 | Closing keyword exists in PR body or commits | FAIL | No closing keyword reference found in PR body or commits. |
| 12 | Cross-repo issues use full form when needed | N/A | No cross-repo linked issues. |
| 13 | All checks are green | PASS | All checks passed (2 checks). |
| 14 | No conflicts with base branch | PASS | mergeable=MERGEABLE, mergeStateStatus=CLEAN |

## B) PR Body Content Requirements

- Status: FAIL
- Evidence: Missing sections: Problem Statement,Linked Issues,Design Notes,Reviewer Guide,Rollout / Risk Notes

## C) Design/Contract Traceability Matrix

| Requirement Source | Requirement | Status | Evidence in PR | Notes |
|---|---|---|---|---|
| docs/qa/FE_WEEK1_CI_MATRIX.md | Document-level coverage heuristic | PASS | doc changed in PR |  |
| docs/qa/FE_TEST_HARNESS_CHECKLIST.md | Document-level coverage heuristic | PARTIAL | doc exists | Provide --traceability-file for requirement-level validation. |

## D) Linked Issue Validation

### Expected Issues from Scope
- vgeshiktor/invoices-codex#7

### Found in PR (Closing References)
- (none)

## E) Review Findings Closure

### Sourcery
- Total threads: 2
- Open threads: 0
- Status: PASS

### Codex
- Total threads: 0
- Open threads: 0
- Status: N/A

## F) CI and Mergeability

- Status checks: 2
- Checks gate: PASS (All checks passed (2 checks).)
- Mergeability gate: PASS (mergeable=MERGEABLE, mergeStateStatus=CLEAN)

## G) Final Verdict

- Overall: FAIL
- Governance gates: 5 passed, 7 failed, 2 n/a (out of 14)
- Content completeness: FAIL
- Design traceability fails: 0
- Design traceability deferred/partial: 1
- Decision: Not ready to merge
