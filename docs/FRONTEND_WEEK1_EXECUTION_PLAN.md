# Frontend Week 1 Execution Plan

Date: 2026-03-09
Scope: Execute `FE-001..FE-007` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 1 Goal

By end of Week 1:
- `apps/web` exists and runs locally.
- frontend quality gates are active (lint/type/test/build).
- app shell + route guard skeleton exists.
- typed API client generation is wired.
- CI enforces frontend checks.

## 2. Team Slots (Fill Names)

- `Owner-FE-A`: frontend foundation lead
- `Owner-FE-B`: quality + CI lead
- `Owner-UX`: shell/layout design pass
- `Owner-Review`: PR reviewer and release gate

## 3. Issue Map (Week 1 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| FE-001 | Scaffold apps/web workspace with Vite + TypeScript | Owner-FE-A | Owner-FE-B | none |
| FE-002 | Add frontend quality gates (ESLint, Prettier, TS strict) | Owner-FE-B | Owner-FE-A | FE-001 |
| FE-003 | Implement app shell and protected route skeleton | Owner-UX | Owner-FE-A | FE-001 |
| FE-004 | Generate typed API client from OpenAPI contract | Owner-FE-A | Owner-FE-B | FE-001 |
| FE-005 | Add global error boundary and fallback UX | Owner-UX | Owner-FE-A | FE-003 |
| FE-006 | Add design tokens and baseline component styles | Owner-UX | Owner-FE-B | FE-003 |
| FE-007 | Add frontend build/test steps to CI pipeline | Owner-FE-B | Owner-Review | FE-002 |

## 4. Day-by-Day Execution

## Day 1 (Mon): Foundation Bootstrap

Planned issues:
- FE-001 (in progress -> done)

Tasks:
1. Create `apps/web` with Vite + TypeScript.
2. Add minimal scripts: `dev`, `build`, `test`, `lint`, `typecheck`.
3. Verify local boot and baseline test command.

End-of-day checkpoint:
- FE-001 done and merged.
- screenshot/log proof of `dev` and `build` success in PR comments.

## Day 2 (Tue): Quality Gates

Planned issues:
- FE-002
- FE-004 (start if FE-001 merged early)

Tasks:
1. Configure ESLint + Prettier + strict TypeScript rules.
2. Add OpenAPI client generation command from `integrations/openapi/saas-openapi.v0.1.0.json`.
3. Add one thin API usage sample with generated client.

End-of-day checkpoint:
- FE-002 merged.
- FE-004 at least 50% complete.

## Day 3 (Wed): App Shell and Guard

Planned issues:
- FE-003
- FE-004 (finish)

Tasks:
1. Implement app layout shell (header/nav/content).
2. Add protected-route skeleton (stub auth state is fine for Week 1).
3. Finish generated API client integration path.

End-of-day checkpoint:
- FE-003 and FE-004 merged.
- route protection and navigation visible in working build.

## Day 4 (Thu): UX Resilience Baseline

Planned issues:
- FE-005
- FE-006

Tasks:
1. Add global error boundary and fallback action.
2. Define tokenized typography, spacing, color variables.
3. Apply tokens to shell components and guard screens.

End-of-day checkpoint:
- FE-005 and FE-006 merged.
- baseline responsive shell works on mobile and desktop widths.

## Day 5 (Fri): CI Enforcement + Closeout

Planned issues:
- FE-007

Tasks:
1. Update CI workflow to include frontend lint/type/test/build.
2. Make checks required for merge.
3. Run full validation and close Week 1 summary.

End-of-day checkpoint:
- FE-007 merged.
- Week 1 status report posted with links to merged PRs.

## 5. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: dependency/tooling risks
- Confidence: `Green | Yellow | Red`

## 6. Definition of Done (Week 1)

For each issue:
- acceptance criteria from issue body met
- tests added/updated where relevant
- docs updated if commands changed
- reviewed and merged

Week-level DoD:
- all `FE-001..FE-007` are closed
- CI frontend checks are required and green
- no open P0/P1 bugs from Week 1 scope

## 7. Risks and Fast Mitigations

- Risk: OpenAPI generation churn from schema changes.
- Mitigation: pin generation to committed schema snapshot for Week 1.

- Risk: CI time increase.
- Mitigation: parallelize lint/type/test steps and cache dependencies.

- Risk: route guard blocked by pending backend auth.
- Mitigation: implement temporary client-side stub guard now; replace in Week 2 with real auth.

## 8. Week 1 Exit Artifacts

At week close, produce:
1. PR list for FE-001..FE-007.
2. CI run link proving required checks.
3. Short retro: what slowed us, what to fix before Week 2.

## 9. Day 0 Inputs (FE1)

Use these Day 0 specs as implementation input for Week 1:

- `docs/frontend/FE_WEEK1_BOOTSTRAP_CHECKLIST.md`
- `docs/frontend/FE_APP_SHELL_ACCEPTANCE.md`

Operational constraint reminder:
- Day 0 produced planning/spec artifacts only; implementation starts on Week 1 Day 1.
