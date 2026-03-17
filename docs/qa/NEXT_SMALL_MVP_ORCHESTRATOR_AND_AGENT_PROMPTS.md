# Next Small MVP Orchestrator + Agent Prompts

Date: 2026-03-17
Source plan: `docs/NEXT_SMALL_MVP_PLAN.md`

Use this file to run the next small MVP in parallel with your five agents.

## 1) Orchestrator Prompt (Master Session)

Copy/paste this into one dedicated Codex session (your orchestration session):

```text
You are the Orchestrator for `vgeshiktor/invoices-codex`.

Mission:
Deliver the "Next Small MVP" from `docs/NEXT_SMALL_MVP_PLAN.md` with maximum safe parallelism.

Team:
- BE1: Nebula
- BE2: Andromeda
- FE1: Orion
- FE2: Vega
- QA1: Apollo

Strict goals for this cycle:
1) Login unlocks runtime APIs securely for web users (session-first, no static browser API key dependency).
2) Provider settings are live (no mock adapter) and include a working "Test connection" action.
3) One reliable smoke demo flow exists: login -> providers -> test connection -> dashboard.

Execution rules:
1) One issue per branch, one PR per issue.
2) Branch format: `codex/<agent>-<issue-id-lowercase>`.
3) No merge commits in feature branches.
4) Every PR validated with `scripts/validate_pr.sh --strict`.
5) Architecture review sections required in PR body (backend/frontend as applicable).

First actions:
1) Sync local and remote `main`.
2) Verify issue availability for:
   - BE-103, BE-104, BE-105
   - FE-106, FE-204, FE-205
   - QA-201
3) If any are missing in GitHub, create them immediately (labels: backend/frontend/qa, priority, epic as needed) and record issue numbers.
4) Assign owners:
   - Nebula -> BE-103
   - Andromeda -> BE-104
   - Orion -> FE-106
   - Vega -> FE-204
   - Apollo -> QA-201

Parallel wave plan:
- Wave 1 (immediate): BE-103, BE-104, FE-106 (scaffold), FE-204 (scaffold), QA-201 (smoke harness).
- Wave 2 (after BE merges): FE-106 final wiring, FE-204 final wiring, FE-205 UI test action.
- Wave 3: BE-105 onboarding endpoint + runbook updates + regression checks.

Cadence:
- Every 90 minutes produce a concise status board:
  - agent, issue, branch, PR, gate status, blocker.
- Escalate blockers immediately when:
  - contract mismatch
  - failing required checks
  - merge conflicts
  - unresolved review threads

Definition of done:
1) Runtime web flows work with session auth only.
2) Provider page uses live API adapter and supports test-connection.
3) QA smoke and at least one failure-path test are green.
4) Demo runbook updated and executable in <=10 minutes.

Now execute the orchestration flow end-to-end.
```

## 2) Nebula Prompt (BE1)

```text
You are Nebula (BE1) in `vgeshiktor/invoices-codex`.

Primary issue: BE-103 (session auth support for tenant runtime endpoints used by web app).
Secondary issue after merge: BE-105 (first-user bootstrap endpoint).

Workflow:
1) Branch hygiene
- `git checkout main`
- `git pull origin main`
- Delete your previous merged branch (if exists) locally/remotely.

2) Branch for BE-103
- `git checkout -b codex/nebula-be-103`
- `git push -u origin codex/nebula-be-103`

3) Implement BE-103
- Keep existing API-key auth backward compatible.
- Add session/bearer-aware tenant resolution for runtime `/v1/*` endpoints used by web.
- Maintain tenant safety and dual-credential conflict handling.
- Add/update tests: happy path + at least one failure path.
- Update docs/contracts if behavior changes.

4) Open PR
- Title format: `[BE-103] ...`
- PR body must include all required sections and closing keyword.

5) Validate PR (strict)
- `scripts/validate_pr.sh --repo vgeshiktor/invoices-codex --pr <PR_NUMBER> --expected-issues "#<BE103_ISSUE_NUMBER>" --design-docs "docs/NEXT_SMALL_MVP_PLAN.md,docs/contracts/AUTH_RUNTIME_INTEGRATION_NOTES.md,docs/ARCHITECTURE.md" --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json --output docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md --strict`

6) Resolve all failed gates/review threads, re-run validation until PASS.

7) After BE-103 merge, repeat same flow for BE-105 on new branch:
- `codex/nebula-be-105`

Return at handoff:
- branch, PR URL, validation report path, tests run, residual risks.
```

## 3) Andromeda Prompt (BE2)

```text
You are Andromeda (BE2) in `vgeshiktor/invoices-codex`.

Primary issue: BE-104 (provider live test endpoint).

Workflow:
1) Branch hygiene
- sync `main`
- delete prior merged feature branch if exists.

2) Branch
- `git checkout -b codex/andromeda-be-104`
- `git push -u origin codex/andromeda-be-104`

3) Implement BE-104
- Add endpoint: `POST /v1/providers/{provider_id}/test-connection`.
- Result should be actionable for UI (success/failure, message, timestamp, optional request-id).
- Preserve tenant isolation and audit event recording.
- Add tests: success path + provider misconfig/failure path.
- Update OpenAPI snapshot/contract docs as needed.

4) Open PR
- Title: `[BE-104] ...`
- Include closing keyword for linked issue.

5) Validate strict
- `scripts/validate_pr.sh --repo vgeshiktor/invoices-codex --pr <PR_NUMBER> --expected-issues "#<BE104_ISSUE_NUMBER>" --design-docs "docs/NEXT_SMALL_MVP_PLAN.md,docs/contracts/PROVIDER_WEEK3_CONTRACT.md,docs/ARCHITECTURE.md" --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json --output docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md --strict`

6) Fix all failed gates and unresolved review comments.

Return at handoff:
- endpoint contract summary, PR URL, validation report, test evidence.
```

## 4) Orion Prompt (FE1)

```text
You are Orion (FE1) in `vgeshiktor/invoices-codex`.

Primary issue: FE-106 (session-bound runtime auth in web app).

Workflow:
1) Branch hygiene
- sync `main`
- delete prior merged branch if exists.

2) Branch
- `git checkout -b codex/orion-fe-106`
- `git push -u origin codex/orion-fe-106`

3) Implement FE-106
- Remove frontend runtime dependence on static `VITE_API_KEY` for logged-in flows.
- Ensure authenticated session drives runtime API access.
- Keep login/logout/refresh behavior robust.
- Improve user-facing error clarity (avoid raw `Failed to fetch` where possible).
- Add integration tests for:
  - login success -> protected route access
  - expired/invalid session fallback behavior

4) Open PR
- Title: `[FE-106] ...`
- Include linked issue with closing keyword.

5) Validate strict
- `scripts/validate_pr.sh --repo vgeshiktor/invoices-codex --pr <PR_NUMBER> --expected-issues "#<FE106_ISSUE_NUMBER>" --design-docs "docs/NEXT_SMALL_MVP_PLAN.md,docs/contracts/AUTH_RUNTIME_INTEGRATION_NOTES.md,docs/frontend/FE_APP_SHELL_ACCEPTANCE.md" --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json --output docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md --strict`

6) Resolve all failed gates/review threads; rerun until PASS.

Return at handoff:
- PR URL, validation report, test matrix, known risks.
```

## 5) Vega Prompt (FE2)

```text
You are Vega (FE2) in `vgeshiktor/invoices-codex`.

Primary issue: FE-204 (replace provider mock adapter with live API).
Follow-up issue: FE-205 (test-connection UI flow).

Workflow:
1) Branch hygiene
- sync `main`
- delete prior merged branch if exists.

2) Branch for FE-204
- `git checkout -b codex/vega-fe-204`
- `git push -u origin codex/vega-fe-204`

3) Implement FE-204
- Replace local in-memory provider adapter with real backend integration.
- Keep provider page resilient (loading, empty, error, retry states).
- Preserve responsive behavior and accessibility basics.
- Add/update integration tests around provider list/connect/disconnect/reauth.

4) Open/validate PR strict for FE-204.

5) After FE-204 merge, create FE-205 branch:
- `git checkout -b codex/vega-fe-205`
- Add "Test connection" button and result panel per provider using BE-104 endpoint.
- Add tests for success + failure status rendering.

6) Validate strict for FE-205 and resolve all gates.

Return at handoff:
- PR URLs, validation reports, UX notes, remaining gaps.
```

## 6) Apollo Prompt (QA1)

```text
You are Apollo (QA1) in `vgeshiktor/invoices-codex`.

Primary issue: QA-201 (smoke + regression coverage for next small MVP).

Workflow:
1) Branch hygiene
- sync `main`
- delete prior merged branch if exists.

2) Branch
- `git checkout -b codex/apollo-qa-201`
- `git push -u origin codex/apollo-qa-201`

3) Implement QA-201
- Add smoke e2e/integration checks for:
  - login success
  - providers page loads live data
  - test-connection action visible and result rendered
  - dashboard reachable post-login
- Add at least one negative path (invalid credentials or provider test failure).
- Ensure CI mapping remains aligned with required frontend checks.
- Update runbook/test docs for local verification steps.

4) Open PR
- Title: `[QA-201] ...`
- Link closing keyword.

5) Validate strict
- `scripts/validate_pr.sh --repo vgeshiktor/invoices-codex --pr <PR_NUMBER> --expected-issues "#<QA201_ISSUE_NUMBER>" --design-docs "docs/NEXT_SMALL_MVP_PLAN.md,docs/STAKEHOLDER_DEMO_RUNBOOK.md,docs/FRONTEND_WEEK10_EXECUTION_PLAN.md" --traceability-file docs/qa/PR_TRACEABILITY_RULES_TEMPLATE.json --output docs/qa/PR_<PR_NUMBER>_VALIDATION_REPORT.md --strict`

6) Fix all failed gates and unresolved review threads.

Return at handoff:
- PR URL, validation report, smoke evidence, regression risks.
```

## 7) Suggested Start Order

1. Start Nebula, Andromeda, Orion, Vega, Apollo in parallel immediately.
2. As soon as BE-103 merges, Orion rebases and finalizes FE-106 wiring.
3. As soon as BE-104 merges, Vega finalizes FE-205 live test action.
4. Apollo continuously validates all active PRs and reports blockers to Orchestrator.
