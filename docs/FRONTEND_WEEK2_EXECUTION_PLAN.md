# Frontend Week 2 Execution Plan

Date: 2026-03-09
Scope: Execute `BE-001`, `FE-101..FE-104` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 2 Goal

By end of Week 2:
- backend auth/session endpoints exist for tenant user login.
- frontend login/logout flow works end-to-end.
- protected routes use real backend session, not Week 1 stub guard.
- role-aware navigation baseline is implemented.
- auth journey has unit/integration/e2e coverage.

## 2. Team Slots (Fill Names)

- `Owner-BE-Auth`: backend auth/session lead
- `Owner-FE-Auth`: frontend auth flow lead
- `Owner-FE-RBAC`: role/permission UX lead
- `Owner-QA`: test automation and CI stability
- `Owner-Review`: cross-stack reviewer and merge gate

## 3. Issue Map (Week 2 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| BE-001 | Implement user/session auth endpoints for tenant login | Owner-BE-Auth | Owner-Review | none |
| FE-101 | Build login/logout UI and protected-route flow | Owner-FE-Auth | Owner-FE-RBAC | BE-001 |
| FE-102 | Implement role-aware navigation and action-level RBAC UX | Owner-FE-RBAC | Owner-FE-Auth | FE-101 |
| FE-103 | Implement secure session storage and renew flow | Owner-FE-Auth | Owner-BE-Auth | FE-101 |
| FE-104 | Add auth unit/integration/e2e test coverage | Owner-QA | Owner-FE-Auth | FE-101 |

## 4. Backend Contract for Week 2 (Freeze Early)

Required endpoints:
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /v1/me`

Required response data:
- authenticated user id
- tenant id
- role list (or primary role)
- session expiry metadata

Security constraints:
- tenant isolation must remain strict.
- invalid/expired session returns `401`.
- all auth actions should produce audit events with request id where available.

## 5. Day-by-Day Execution

## Day 1 (Mon): Auth Contract + Backend Skeleton

Planned issues:
- BE-001 (start)

Tasks:
1. Finalize request/response contract for auth endpoints.
2. Add backend auth/session models and migration skeleton.
3. Implement `POST /auth/login` + `GET /v1/me` happy path.

End-of-day checkpoint:
- contract frozen and documented in issue comments.
- backend PR opened with passing tests for login + me.

## Day 2 (Tue): Backend Completion + Frontend Login Start

Planned issues:
- BE-001 (finish)
- FE-101 (start)

Tasks:
1. Finish `refresh` and `logout` endpoints.
2. Add backend auth error handling (`401`, `403`) and tenant safety tests.
3. Build frontend login page and wire submit to backend login endpoint.

End-of-day checkpoint:
- BE-001 merged.
- FE-101 at least 50% complete.

## Day 3 (Wed): Protected Routes + Session Wiring

Planned issues:
- FE-101 (finish)
- FE-103 (start)

Tasks:
1. Replace Week 1 stub guard with real auth state.
2. Implement logout path and protected route redirects.
3. Add secure session handling and refresh path integration.

End-of-day checkpoint:
- FE-101 merged.
- FE-103 in review or near complete.

## Day 4 (Thu): RBAC UX + Session Hardening

Planned issues:
- FE-102
- FE-103 (finish)

Tasks:
1. Implement role-aware navigation and restricted action handling.
2. Finish session renewal and expiry handling UX.
3. Validate edge cases: expired session, unauthorized role, multi-tab logout.

End-of-day checkpoint:
- FE-102 and FE-103 merged.
- no open P0/P1 auth defects.

## Day 5 (Fri): Auth Test Matrix + Closeout

Planned issues:
- FE-104

Tasks:
1. Add unit tests for auth state/hooks/components.
2. Add integration tests for login/logout/refresh flows.
3. Add e2e for critical auth journey and flaky-test stabilization.

End-of-day checkpoint:
- FE-104 merged.
- Week 2 status report posted with PR links and CI run links.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: contract/backend/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 2)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- docs updated if API contract changed
- reviewed and merged

Week-level DoD:
- `BE-001`, `FE-101`, `FE-102`, `FE-103`, `FE-104` all closed
- frontend uses backend auth endpoints in default flow
- auth e2e runs in CI and is required
- no open P0/P1 auth bugs

## 8. Test Matrix (Minimum)

- Unit:
  - auth state management
  - role-to-navigation mapping
  - guard redirect behavior
- Integration:
  - login success/failure
  - refresh token/session renewal
  - logout invalidation
- E2E:
  - user can login -> access protected page -> logout
  - expired session redirects to login
  - unauthorized role blocks restricted action

## 9. Risks and Fast Mitigations

- Risk: backend auth contract churn mid-week.
- Mitigation: freeze contract on Day 1 and version any required changes.

- Risk: session handling bugs across tabs/devices.
- Mitigation: include multi-tab scenario in FE-104 and manual QA checklist.

- Risk: RBAC complexity stalls Week 2.
- Mitigation: implement minimal role matrix now; defer fine-grained permissions to Week 3+.

## 10. Week 2 Exit Artifacts

At week close, produce:
1. merged PR list for `BE-001`, `FE-101..FE-104`.
2. CI links proving auth checks are required and green.
3. short auth hardening note before entering Week 3 provider work.
