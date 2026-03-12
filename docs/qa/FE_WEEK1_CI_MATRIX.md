# FE Week 1 CI Matrix (`FE-007`)

Prepared by: Apollo (QA1)
Prepared on: 2026-03-11
Scope lock: Day 0 prep/spec only (no CI workflow edits in this document)

## 1. Purpose

Define an executable Week 1 frontend CI check matrix for `FE-007` so Day 1 implementation can add required checks with minimal ambiguity.

## 2. Inputs and Constraints

Source documents:
- `docs/FRONTEND_PARALLEL_EXECUTION_MATRIX.md`
- `docs/FRONTEND_WEEK1_EXECUTION_PLAN.md`
- `.github/workflows/ci.yml`

Current state in `ci.yml` (2026-03-11):
- CI already runs Go and Python checks.
- CI does **not** run frontend checks yet.

Constraint:
- Day 0 is specification only; no workflow behavior changes here.

## 3. Current CI Gaps (to close on Day 1)

1. No Node toolchain setup in CI.
2. No frontend dependency install step.
3. No frontend lint/type/unit/build checks.
4. No frontend required check names defined for branch protection.

## 4. Week 1 Frontend CI Check Matrix

Script contract (from `apps/web/package.json`):
- `lint`
- `typecheck`
- `test` (unit via Vitest)
- `build`

| Check ID | GitHub check name (target) | Command | Blocking | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| FE-CI-01 | `frontend / lint` | `npm run lint` | Required | FE2 + QA1 | Includes ESLint (and Prettier verification if wired via lint script). |
| FE-CI-02 | `frontend / typecheck` | `npm run typecheck` | Required | FE2 + QA1 | Must run with strict TypeScript config from `FE-002`. |
| FE-CI-03 | `frontend / unit` | `npm run test -- --run` | Required | FE2 + QA1 | Non-watch mode; deterministic output for CI logs. |
| FE-CI-04 | `frontend / build` | `npm run build` | Required | FE1 + FE2 | Verifies production compile path for app shell baseline. |

## 5. Proposed Day 1 CI Job Shape (Spec)

Recommended topology (implementation target for Day 1):
1. Add a dedicated `frontend` job in `.github/workflows/ci.yml`.
2. Use Node `20.x` (aligned with `docs/frontend/FE_WEEK1_BOOTSTRAP_CHECKLIST.md`).
3. Set `working-directory: apps/web` for frontend commands.
4. Execute FE checks as a matrix (`lint`, `typecheck`, `unit`, `build`) for isolation and parallelism.
5. Keep existing backend checks unchanged.

Suggested matrix values:
- `check: [lint, typecheck, unit, build]`

Command mapping:
- `lint -> npm run lint`
- `typecheck -> npm run typecheck`
- `unit -> npm run test -- --run`
- `build -> npm run build`

## 6. Merge Gate Criteria (Week 1)

A PR touching frontend scope (`apps/web/**`, frontend config, or shared contracts consumed by FE) can be merged only when:

1. Existing required backend checks are green.
2. All four frontend checks are green:
   - `frontend / lint`
   - `frontend / typecheck`
   - `frontend / unit`
   - `frontend / build`
3. No unresolved `P0`/`P1` defects linked to the PR.
4. No skipped required checks and no force-merge override without explicit incident note.

Week 1 closure gate (`FE-007` done):
- Frontend checks are marked required in branch protection.
- At least one merged PR shows all required frontend checks passing in CI.

## 7. Failure Triage Flow (Week 1)

Trigger:
- Any required frontend CI check fails on PR or default branch.

Ownership model:
- First responder: PR author (or last committer on broken branch).
- QA owner: Apollo (QA1) coordinates classification and flake tracking.
- Escalation owner: FE lead (Orion) if unresolved inside SLA.

Flow:
1. Classify failure in first pass (target: within 15 minutes):
   - `CODE`: real product/regression issue.
   - `TEST`: unstable or incorrect test.
   - `INFRA`: environment/tooling/workflow issue.
2. Apply immediate action:
   - `CODE`: fix in same PR or revert offending change.
   - `TEST`: stabilize test (remove timing nondeterminism, update fixtures/mocks) and rerun.
   - `INFRA`: patch workflow/tooling and rerun; if systemic, open incident ticket.
3. Escalate if unresolved after 2 hours:
   - Notify FE lead + QA1 in team channel.
   - Freeze merges affecting frontend until required checks are healthy.
4. Closeout requirements for recurring failures:
   - Record root cause and preventive action in PR comment or incident note.
   - Link follow-up issue for non-trivial remediation.

## 8. Day 1 CI Implementation Order

1. Add `frontend` job with `actions/setup-node@v4` and Node `20.x`.
2. Run deterministic install in `apps/web` (`npm ci`).
3. Add matrix steps for `lint`, `typecheck`, `unit`, and `build`.
4. Confirm check run names exactly match Section 4.
5. Validate one green PR run.
6. Mark FE checks as required in branch protection.

## 9. Day 1 Verification Checklist

- [ ] `frontend / lint` appears and passes.
- [ ] `frontend / typecheck` appears and passes.
- [ ] `frontend / unit` appears and passes.
- [ ] `frontend / build` appears and passes.
- [ ] Required-status enforcement confirmed in repository settings.
- [ ] One CI run link attached to `FE-007` issue.

## 10. Branch Protection Mapping (Week 1)

Required status checks to configure after first stable green run:
1. `frontend / lint`
2. `frontend / typecheck`
3. `frontend / unit`
4. `frontend / build`

Recommended branch protection settings:
- Require status checks before merging: enabled.
- Require branches to be up to date before merging: enabled.
- Require conversation resolution before merging: enabled.
- Include administrators: enabled.

## 11. Triage Communication Template

Use this template in PR comments or team channel when a required FE check fails:

```text
[CI-FE] Failure Report
- Check: <frontend / lint|typecheck|unit|build>
- Classification: <CODE|TEST|INFRA>
- First seen: <timestamp>
- Owner: <assignee>
- Immediate action: <fix/retry/revert>
- Escalation needed: <yes/no>
- ETA to green: <time>
```

## 12. Day 1 Exit Criteria

Day 1 CI implementation is complete only when:
1. All four frontend checks run on every PR.
2. All four checks are required in branch protection.
3. At least one merged frontend PR proves green required checks.
4. Any failure during rollout has triage notes using Section 11 template.
