# PR Validation Report

Date: 2026-03-12
PR: https://github.com/vgeshiktor/invoices-codex/pull/49
Repository: vgeshiktor/invoices-codex

## Inputs
- PR Number: 49
- Base/Head: main <- codex/vega
- Expected issues: vgeshiktor/invoices-codex#4
- Design docs: docs/frontend/FE_OPENAPI_CLIENT_PLAN.md,docs/frontend/FE_ENV_TEMPLATE.md
- Traceability rules: (not provided)

## A) PR Governance Checklist (14 Gates)

| # | Validation Item | Status | Evidence |
|---|---|---|---|
| 1 | PR title format matches team convention | FAIL | Title does not match expected format [FE-xxx]/[BE-xxx]: FE Day 0 + FE-004 setup: OpenAPI client path, env templates, and web scaffold |
| 2 | PR summary follows documentation guidelines | FAIL | Missing required sections: Problem Statement,Design Notes,Testing,Rollout/Risk Notes |
| 3 | Commit messages follow naming convention | FAIL | Non-conforming commit headlines: Merge branch 'main' into codex/vega |
| 4 | Reviewer guide exists and is actionable | FAIL | Reviewer guide section not found in PR body. |
| 5 | File-level changes are scoped/aligned | PASS | Changed files: 39. Top files: apps/web/.env.development (+5/-0);apps/web/.env.example (+8/-0);apps/web/.env.staging (+5/-0);apps/web/.gitignore (+24/-0);apps/web/README.md (+73/-0);apps/web/eslint.config.js (+23/-0);apps/web/index.html (+13/-0);apps/web/package-lock.json (+3861/-0);apps/web/package.json (+34/-0);apps/web/public/vite.svg (+1/-0);apps/web/src/App.css (+71/-0);apps/web/src/App.tsx (+127/-0) |
| 6 | Linked issues are correct | PASS | No unexpected linked issues. |
| 7 | Linked issues are complete | FAIL | Missing expected linked issues: vgeshiktor/invoices-codex#4 |
| 8 | Sourcery review findings resolved | FAIL | Unresolved Sourcery threads: 1 of 6. |
| 9 | Codex review findings resolved | PASS | All Codex threads resolved (1/1). |
| 10 | PR summary lists resolved issues with closing keywords | FAIL | No closing issue references found in PR metadata. |
| 11 | Closing keyword exists in PR body or commits | FAIL | No closing keyword reference found in PR body or commits. |
| 12 | Cross-repo issues use full form when needed | N/A | No cross-repo linked issues. |
| 13 | All checks are green | PASS | All checks passed (3 checks). |
| 14 | No conflicts with base branch | PASS | mergeable=MERGEABLE, mergeStateStatus=CLEAN |

## B) PR Body Content Requirements

- Status: FAIL
- Evidence: Missing sections: Problem Statement,Linked Issues,Design Notes,Reviewer Guide,Testing,Rollout / Risk Notes

## C) Design/Contract Traceability Matrix

| Requirement Source | Requirement | Status | Evidence in PR | Notes |
|---|---|---|---|---|
| docs/frontend/FE_OPENAPI_CLIENT_PLAN.md | Document-level coverage heuristic | PASS | doc changed in PR |  |
| docs/frontend/FE_ENV_TEMPLATE.md | Document-level coverage heuristic | PARTIAL | doc exists | Provide --traceability-file for requirement-level validation. |

## D) Linked Issue Validation

### Expected Issues from Scope
- vgeshiktor/invoices-codex#4

### Found in PR (Closing References)
- (none)

## E) Review Findings Closure

### Sourcery
- Total threads: 6
- Open threads: 1
- Status: FAIL

### Codex
- Total threads: 1
- Open threads: 0
- Status: PASS

## F) CI and Mergeability

- Status checks: 3
- Checks gate: PASS (All checks passed (3 checks).)
- Mergeability gate: PASS (mergeable=MERGEABLE, mergeStateStatus=CLEAN)

## G) Final Verdict

- Overall: FAIL
- Governance gates: 5 passed, 8 failed, 1 n/a (out of 14)
- Content completeness: FAIL
- Design traceability fails: 0
- Design traceability deferred/partial: 1
- Decision: Not ready to merge
