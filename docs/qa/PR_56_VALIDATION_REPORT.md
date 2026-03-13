# PR Validation Report

Date: 2026-03-12
PR: https://github.com/vgeshiktor/invoices-codex/pull/56
Repository: vgeshiktor/invoices-codex

## Inputs
- PR Number: 56
- Base/Head: main <- codex/orion-fe-001
- Expected issues: vgeshiktor/invoices-codex#1
- Design docs: docs/FRONTEND_CONVERSION_BACKLOG.md,docs/FRONTEND_WEEK1_EXECUTION_PLAN.md,docs/FRONTEND_PARALLEL_EXECUTION_MATRIX.md
- Traceability rules: docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json

## A) PR Governance Checklist (14 Gates)

| # | Validation Item | Status | Evidence |
|---|---|---|---|
| 1 | PR title format matches team convention | PASS | Title: [FE-001] Scaffold apps/web workspace with Vite + TypeScript |
| 2 | PR summary follows documentation guidelines | PASS | Required sections found: problem, design, testing, rollout/risk. |
| 3 | Commit messages follow naming convention | PASS | All commit headlines match convention. |
| 4 | Reviewer guide exists and is actionable | PASS | Reviewer guide section found. |
| 5 | File-level changes are scoped/aligned | PASS | Changed files: 19. Top files: apps/web/.gitignore (+24/-0);apps/web/README.md (+73/-0);apps/web/eslint.config.js (+23/-0);apps/web/index.html (+13/-0);apps/web/package-lock.json (+3641/-0);apps/web/package.json (+34/-0);apps/web/public/vite.svg (+1/-0);apps/web/src/App.css (+42/-0);apps/web/src/App.tsx (+35/-0);apps/web/src/assets/react.svg (+1/-0);apps/web/src/index.css (+68/-0);apps/web/src/lib/env.test.ts (+17/-0) |
| 6 | Linked issues are correct | PASS | No unexpected linked issues. |
| 7 | Linked issues are complete | PASS | All expected issues are linked. |
| 8 | Sourcery review findings resolved | PASS | All Sourcery threads resolved (2/2). |
| 9 | Codex review findings resolved | PASS | All Codex threads resolved (1/1). |
| 10 | PR summary lists resolved issues with closing keywords | PASS | All linked issues are listed with closing keywords in PR body. |
| 11 | Closing keyword exists in PR body or commits | PASS | Closing keyword reference found in PR body/commits. |
| 12 | Cross-repo issues use full form when needed | N/A | No cross-repo linked issues. |
| 13 | All checks are green | PASS | All checks passed (3 checks). |
| 14 | No conflicts with base branch | PASS | mergeable=MERGEABLE, mergeStateStatus=CLEAN |

## B) PR Body Content Requirements

- Status: PASS
- Evidence: All required PR body sections found.

## C) Design/Contract Traceability Matrix

| Requirement Source | Requirement | Status | Evidence in PR | Notes |
|---|---|---|---|---|
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement POST /auth/login endpoint | FAIL | No pattern matched in scope 'diff'. | Adjust patterns for your framework if route declaration style differs. |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement POST /auth/refresh endpoint | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement POST /auth/logout endpoint | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement GET /v1/me endpoint | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Error envelope includes code/message/request_id | PARTIAL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_MIGRATION_SCOPE.md | Add saas_users table | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_MIGRATION_SCOPE.md | Add saas_tenant_memberships table | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_MIGRATION_SCOPE.md | Add saas_auth_sessions table | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | AUTH_RATE_LIMITED is explicitly deferred/documented | DEFERRED | No pattern matched in scope 'diff'. | Use DEFERRED/PARTIAL for consciously postponed contract items. |

## D) Linked Issue Validation

### Expected Issues from Scope
- vgeshiktor/invoices-codex#1

### Found in PR (Closing References)
- vgeshiktor/invoices-codex#1

## E) Review Findings Closure

### Sourcery
- Total threads: 2
- Open threads: 0
- Status: PASS

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
- Governance gates: 13 passed, 0 failed, 1 n/a (out of 14)
- Content completeness: PASS
- Design traceability fails: 7
- Design traceability deferred/partial: 2
- Decision: Not ready to merge
