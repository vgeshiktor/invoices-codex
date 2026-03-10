# Frontend Parallel Execution Matrix (Resource-Loaded, Named Team)

Date: 2026-03-10
Assumption: 5-person delivery team (all full-time, ~40h/week)

Named role mapping:

- `BE1` -> `Nebula` (~40h/week): backend platform/domain APIs
- `BE2` -> `Andromeda` (~40h/week): backend integrations/runtime workers
- `FE1` -> `Orion` (~40h/week): frontend core UX/app architecture
- `FE2` -> `Vega` (~40h/week): frontend feature flows/state management
- `QA1` -> `Apollo` (~40h/week): QA/DevEx automation and CI gates

Calendar assumption (start-date aligned):

- Kickoff day: Tuesday, 2026-03-10
- Week 1 execution starts Monday, 2026-03-16
- Week 10 execution ends Friday, 2026-05-22

## 0. Kickoff Day 0 (2026-03-10)

| Person | Role | Day-0 Assignment |
| --- | --- | --- |
| Nebula | BE1 | Freeze Week 2 auth API contract draft and migration scope. |
| Andromeda | BE2 | Prepare runtime/auth integration notes and edge-case list. |
| Orion | FE1 | Prepare `apps/web` bootstrap checklist and app-shell acceptance criteria. |
| Vega | FE2 | Prepare OpenAPI client generation path and frontend env template. |
| Apollo | QA1 | Prepare CI check matrix and Week 1 test harness checklist. |

Day-0 exit criteria:
1. Week 1 backlog order confirmed.
2. Week 2 auth contract draft ready for implementation start.
3. CI/test ownership and daily integration window confirmed.

## 1. Critical Path (Do Not Slip)

1. `BE-001` -> `FE-101..FE-103`
2. `BE-101/BE-102` -> `FE-201/FE-202`
3. `BE-201/BE-202` -> `FE-301..FE-304`
4. `BE-301/BE-302` -> `FE-501..FE-503`
5. `BE-401` -> `FE-604`

## 2. Week-by-Week Parallel Matrix

## Week 1 (2026-03-16 .. 2026-03-20) - Foundation (`FE-001..FE-007`)

| Day | BE1                      | BE2                       | FE1                                       | FE2                                              | QA1                                              |
| --- | ------------------------ | ------------------------- | ----------------------------------------- | ------------------------------------------------ | ------------------------------------------------ |
| Mon | Review FE contract needs | Draft Week2 auth API spec | Scaffold `apps/web` (`FE-001`)        | Setup scripts/env (`FE-001`)                   | Setup frontend CI job skeleton                   |
| Tue | OpenAPI review support   | Auth data model draft     | Lint/TS strict setup (`FE-002`)         | API client codegen bootstrap (`FE-004`)        | Baseline test command in CI                      |
| Wed | Week2 endpoint stubs     | Session strategy draft    | App shell + route guard stub (`FE-003`) | Wire generated client into one page (`FE-004`) | Smoke test matrix (unit/integration placeholder) |
| Thu | PR review                | PR review                 | Error boundary/fallback (`FE-005`)      | Design tokens baseline (`FE-006`)              | RTL/MSW test harness prep                        |
| Fri | Week2 contract freeze    | Week2 contract freeze     | CI integration (`FE-007`)               | Week1 polish + bugfix                            | Week1 regression + CI gate validation            |

## Week 2 (2026-03-23 .. 2026-03-27) - Auth (`BE-001`, `FE-101..FE-104`)

| Day | BE1                           | BE2                                            | FE1                                 | FE2                                         | QA1                                      |
| --- | ----------------------------- | ---------------------------------------------- | ----------------------------------- | ------------------------------------------- | ---------------------------------------- |
| Mon | Implement `/auth/login`     | Add auth/session schema + migration            | Login page UI skeleton (`FE-101`) | Auth state store + guard integration        | Auth test plan + fixtures                |
| Tue | Implement `/v1/me` + errors | Implement `/auth/refresh` + `/auth/logout` | Login form validation/errors        | Session persistence/renew flow (`FE-103`) | MSW auth mocks + integration scaffolding |
| Wed | Tenant-isolation auth tests   | Auth audit event hooks                         | Protected route final wiring        | Logout + expiry redirect UX                 | Integration tests login/logout/refresh   |
| Thu | Bugfix + hardening            | Contract docs update                           | RBAC navigation (`FE-102`)        | Session edge cases (`FE-103`)             | E2E auth journey (`FE-104`)            |
| Fri | Merge support                 | Merge support                                  | Auth UX polish                      | Auth bugfixes                               | Stabilize + require auth checks in CI    |

## Week 3 (2026-03-30 .. 2026-04-03) - Providers (`BE-101`, `BE-102`, `FE-201..FE-203`)

| Day | BE1                            | BE2                               | FE1                                  | FE2                              | QA1                                  |
| --- | ------------------------------ | --------------------------------- | ------------------------------------ | -------------------------------- | ------------------------------------ |
| Mon | Provider model + CRUD GET/POST | OAuth flow contract + state model | Provider settings shell (`FE-201`) | Provider card/status UI          | Provider flow test harness           |
| Tue | CRUD PATCH/DELETE + tests      | OAuth start endpoints             | Connect/disconnect action wiring     | Health/error badges (`FE-202`) | Integration tests for provider CRUD  |
| Wed | Provider health fields output  | OAuth callback/refresh/revoke     | Complete connect/re-auth flow        | Error-state UX + retries         | Start e2e Gmail/Outlook (`FE-203`) |
| Thu | Security masking review        | OAuth hardening + edge cases      | Finish FE-201                        | Finish FE-202                    | Expand e2e coverage + flake fixes    |
| Fri | Merge support                  | Merge support                     | Provider UX polish                   | Provider UX polish               | Make provider e2e required in CI     |

## Week 4 (2026-04-06 .. 2026-04-10) - Collection Baseline (`BE-201`, `FE-301`, `FE-302`)

| Day | BE1                              | BE2                                         | FE1                                    | FE2                                  | QA1                               |
| --- | -------------------------------- | ------------------------------------------- | -------------------------------------- | ------------------------------------ | --------------------------------- |
| Mon | Collection job model + migration | Create endpoint (`POST /collection-jobs`) | Wizard step 1 (providers) (`FE-301`) | Wizard step 2 (month scope)          | Collection fixtures + API mocks   |
| Tue | List/get endpoints               | Lifecycle transition tests                  | Wizard submit flow                     | Create error states/ack view         | Integration tests create/list/get |
| Wed | Contract finalization            | Merge BE-201                                | Finish FE-301                          | Start run detail screen (`FE-302`) | E2E baseline create->detail       |
| Thu | Support bugfix                   | Support bugfix                              | Run detail timeline/status             | Polling/refresh controls             | Failure-state rendering tests     |
| Fri | Stability support                | Stability support                           | FE-302 polish                          | Mobile responsive tuning             | CI gate for collection baseline   |

## Week 5 (2026-04-13 .. 2026-04-17) - Retry/Orchestration (`BE-202`, `FE-303`, `FE-304`)

| Day | BE1                                   | BE2                            | FE1                                    | FE2                            | QA1                               |
| --- | ------------------------------------- | ------------------------------ | -------------------------------------- | ------------------------------ | --------------------------------- |
| Mon | Wire collection -> provider executors | Persist counters + parse links | Retry CTA + state machine (`FE-303`) | Original/retry run relation UI | Retry scenario fixtures           |
| Tue | Retry endpoint implementation         | Idempotency guard for retries  | Wire retry API + UX states             | User-safe error mapping        | Integration tests retry paths     |
| Wed | Failure normalization                 | Retry audit events + hardening | Complete FE-303                        | FE-303 polish + edge handling  | E2E happy/fail/retry (`FE-304`) |
| Thu | Orchestration bugfix                  | Orchestration bugfix           | Retry UX bugfix                        | Retry UX bugfix                | Flake stabilization               |
| Fri | Merge support                         | Merge support                  | Collection flow polish                 | Collection flow polish         | Require retry suite in CI         |

## Week 6 (2026-04-20 .. 2026-04-24) - Reports (`FE-401..FE-405`)

| Day | BE1                | BE2                | FE1                               | FE2                                 | QA1                           |
| --- | ------------------ | ------------------ | --------------------------------- | ----------------------------------- | ----------------------------- |
| Mon | API support buffer | API support buffer | Report builder form (`FE-401`)  | Format/filter controls (`FE-401`) | Report fixture dataset        |
| Tue | API clarifications | API clarifications | Complete FE-401                   | Report list screen (`FE-402`)     | Integration tests create/list |
| Wed | Support bugfix     | Support bugfix     | Report detail/status (`FE-402`) | Download actions (`FE-403`)       | Start e2e create->status      |
| Thu | Support bugfix     | Support bugfix     | Totals/VAT cards (`FE-404`)     | Finish downloads (`FE-403`)       | Cross-browser download tests  |
| Fri | Support merge      | Support merge      | Report UX polish                  | Report UX polish                    | FE-405 finalize + CI required |

## Week 7 (2026-04-27 .. 2026-05-01) - Schedules Baseline (`BE-301`, `FE-501`, `FE-502`)

| Day | BE1                        | BE2                                 | FE1                              | FE2                                         | QA1                             |
| --- | -------------------------- | ----------------------------------- | -------------------------------- | ------------------------------------------- | ------------------------------- |
| Mon | Schedule model + migration | Schedule create/list endpoints      | Schedule form shell (`FE-501`) | History shell (`FE-502`)                  | Timezone fixture pack           |
| Tue | Schedule get/update        | Pause/resume endpoints + validation | Create/edit schedule flow        | Pause/resume actions                        | Integration tests schedule CRUD |
| Wed | Contract + bugfix          | Merge BE-301                        | Finish FE-501                    | Build next/last run visibility (`FE-502`) | E2E baseline schedule flow      |
| Thu | Support bugfix             | Support bugfix                      | Responsive schedule form         | Finish FE-502                               | History/state tests             |
| Fri | Merge support              | Merge support                       | Schedule UX polish               | Schedule UX polish                          | Gate schedule baseline checks   |

## Week 8 (2026-05-04 .. 2026-05-08) - Runtime Scheduling (`BE-302`, `FE-503`)

| Day | BE1                              | BE2                                 | FE1                     | FE2                         | QA1                               |
| --- | -------------------------------- | ----------------------------------- | ----------------------- | --------------------------- | --------------------------------- |
| Mon | Scheduler runtime loop           | Duplicate-trigger idempotency lock  | Runtime status UI hints | Run linkage display support | Time-freeze test harness          |
| Tue | Update next/last run metadata    | Persist schedule_id linkage on runs | Runtime UX bugfix       | Runtime UX bugfix           | Integration tests runtime linkage |
| Wed | Error handling hardening + merge | Hardening + merge                   | Support                 | Support                     | Start FE-503 e2e build            |
| Thu | Support bugfix                   | Support bugfix                      | E2E fix support         | E2E fix support             | Expand FE-503 scenarios           |
| Fri | Merge support                    | Merge support                       | Final polish            | Final polish                | Require runtime scheduling e2e    |

## Week 9 (2026-05-11 .. 2026-05-15) - Observability (`BE-401`, `FE-601..FE-605`)

| Day | BE1                                        | BE2                      | FE1                                   | FE2                                          | QA1                                     |
| --- | ------------------------------------------ | ------------------------ | ------------------------------------- | -------------------------------------------- | --------------------------------------- |
| Mon | Audit query endpoint baseline (`BE-401`) | Masking/pagination logic | Telemetry taxonomy draft (`FE-601`) | Request ID UI stubs (`FE-603`)             | Observability test plan                 |
| Tue | Audit endpoint finalization                | Performance tuning       | OTel instrumentation (`FE-602`)     | Error reporting instrumentation (`FE-602`) | Taxonomy validation + integration tests |
| Wed | Support bugfix                             | Support bugfix           | Finish FE-602                         | Finish FE-603                                | Correlation flow tests                  |
| Thu | Support FE-604 API needs                   | Support FE-604 API needs | Timeline data + filters (`FE-604`)  | Support bundle export (`FE-605`)           | E2E timeline/support bundle             |
| Fri | Merge support                              | Merge support            | FE-604 polish                         | FE-605 polish                                | Require traceability checks in CI       |

## Week 10 (2026-05-18 .. 2026-05-22) - Quality and Release (`FE-701..FE-705`)

| Day | BE1              | BE2              | FE1                                  | FE2                         | QA1                                               |
| --- | ---------------- | ---------------- | ------------------------------------ | --------------------------- | ------------------------------------------------- |
| Mon | Release support  | Release support  | Fix test debt                        | Fix test debt               | Enforce test pyramid in CI (`FE-701`)           |
| Tue | Release support  | Release support  | Coverage gap fixes                   | Coverage gap fixes          | Coverage gate >=80% (`FE-702`)                  |
| Wed | A11y fix support | A11y fix support | Automated a11y checks (`FE-703`)   | Manual a11y fixes/checklist | A11y verification + sign-off                      |
| Thu | Perf fix support | Perf fix support | Lighthouse budget setup (`FE-704`) | Perf optimization fixes     | Perf gate validation in CI                        |
| Fri | Go-live support  | Go-live support  | Final polish                         | Final polish                | Release checklist + rollback runbook (`FE-705`) |

## 3. Operating Rules for Parallel Work

1. Freeze weekly API contracts every Monday 12:00.
2. One daily integration window at 16:00 for branch merges + smoke checks.
3. No schema changes after Wednesday without explicit change notice.
4. Keep WIP limit: max 2 active tickets per person.
5. CI red on required checks blocks all merges.

## 4. Weekly Exit Gate (Common)

A week is done only when:

1. all issues for that week are merged,
2. required CI checks are green,
3. no open P0/P1 defects in that week scope,
4. handoff note for next week is published.
