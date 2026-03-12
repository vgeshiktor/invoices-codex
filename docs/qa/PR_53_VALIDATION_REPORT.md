# PR Validation Report

Date: 2026-03-11
PR: https://github.com/vgeshiktor/invoices-codex/pull/53
Repository: vgeshiktor/invoices-codex

## Inputs
- PR Number: 53
- Base/Head: main <- codex/nebula-be-101
- Expected issues: vgeshiktor/invoices-codex#13
- Design docs: docs/contracts/PROVIDER_WEEK3_CONTRACT.md,docs/FRONTEND_WEEK3_EXECUTION_PLAN.md,docs/FRONTEND_CONVERSION_BACKLOG.md
- Traceability rules: docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json

## A) PR Governance Checklist (14 Gates)

| # | Validation Item | Status | Evidence |
|---|---|---|---|
| 1 | PR title format matches team convention | PASS | Title: [BE-101] Add provider configuration domain and tenant-scoped CRUD APIs |
| 2 | PR summary follows documentation guidelines | PASS | Required sections found: problem, design, testing, rollout/risk. |
| 3 | Commit messages follow naming convention | PASS | All commit headlines match convention. |
| 4 | Reviewer guide exists and is actionable | PASS | Reviewer guide section found. |
| 5 | File-level changes are scoped/aligned | PASS | Changed files: 11. Top files: apps/workers-py/migrations/versions/20260311_0003_provider_configs.py (+65/-0);apps/workers-py/src/invplatform/saas/api.py (+130/-1);apps/workers-py/src/invplatform/saas/db.py (+2/-0);apps/workers-py/src/invplatform/saas/models.py (+34/-0);apps/workers-py/src/invplatform/saas/service.py (+250/-0);docs/contracts/PROVIDER_WEEK3_CONTRACT.md (+110/-0);docs/qa/PR_53_VALIDATION_REPORT.md (+85/-0);tests/test_saas_api.py (+80/-0);tests/test_saas_openapi_export.py (+1/-0);tests/test_saas_service.py (+94/-1);tests/test_saas_tenant_guard.py (+38/-1) |
| 6 | Linked issues are correct | PASS | No unexpected linked issues. |
| 7 | Linked issues are complete | PASS | All expected issues are linked. |
| 8 | Sourcery review findings resolved | N/A | No Sourcery review threads found. |
| 9 | Codex review findings resolved | N/A | No Codex review threads found. |
| 10 | PR summary lists resolved issues with closing keywords | PASS | All linked issues are listed with closing keywords in PR body. |
| 11 | Closing keyword exists in PR body or commits | PASS | Closing keyword reference found in PR body/commits. |
| 12 | Cross-repo issues use full form when needed | N/A | No cross-repo linked issues. |
| 13 | All checks are green | FAIL | Failing/non-success checks: build-test: IN_PROGRESS/;build-test: IN_PROGRESS/ |
| 14 | No conflicts with base branch | FAIL | mergeable=MERGEABLE, mergeStateStatus=UNSTABLE |

## B) PR Body Content Requirements

- Status: PASS
- Evidence: All required PR body sections found.

## C) Design/Contract Traceability Matrix

| Requirement Source | Requirement | Status | Evidence in PR | Notes |
|---|---|---|---|---|
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement POST /auth/login endpoint | FAIL | No pattern matched in scope 'diff'. | Adjust patterns for your framework if route declaration style differs. |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement POST /auth/refresh endpoint | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement POST /auth/logout endpoint | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Implement GET /v1/me endpoint | PASS | Matched pattern: def get_me\( |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | Error envelope includes code/message/request_id | PASS | Matched pattern: "error" |  |
| docs/contracts/AUTH_WEEK2_MIGRATION_SCOPE.md | Add saas_users table | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_MIGRATION_SCOPE.md | Add saas_tenant_memberships table | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_MIGRATION_SCOPE.md | Add saas_auth_sessions table | FAIL | No pattern matched in scope 'diff'. |  |
| docs/contracts/AUTH_WEEK2_CONTRACT.md | AUTH_RATE_LIMITED is explicitly deferred/documented | DEFERRED | No pattern matched in scope 'diff'. | Use DEFERRED/PARTIAL for consciously postponed contract items. |

## D) Linked Issue Validation

### Expected Issues from Scope
- vgeshiktor/invoices-codex#13

### Found in PR (Closing References)
- vgeshiktor/invoices-codex#13

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

- Status checks: 2
- Checks gate: FAIL (Failing/non-success checks: build-test: IN_PROGRESS/;build-test: IN_PROGRESS/)
- Mergeability gate: FAIL (mergeable=MERGEABLE, mergeStateStatus=UNSTABLE)

## G) Final Verdict

- Overall: FAIL
- Governance gates: 9 passed, 2 failed, 3 n/a (out of 14)
- Content completeness: PASS
- Design traceability fails: 6
- Design traceability deferred/partial: 1
- Decision: Not ready to merge
