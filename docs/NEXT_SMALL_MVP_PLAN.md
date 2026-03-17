# Next Small MVP Plan (Usability Recovery)

Date: 2026-03-17
Owner: Product/Engineering

## 1) MVP Goal

Make the web app actually usable for tenant operators in local demo mode by fixing two blockers:

1. Login must unlock runtime APIs securely (no manual hardcoded API key setup).
2. Provider settings must support real connection checks with a clear "Test connection" action.

## 2) Current Critical Gaps (P0)

1. Auth/runtime mismatch:
   - Web login uses `/auth/login` (session/bearer), but most `/v1/*` endpoints still depend on `X-API-Key`.
   - Result: user can login but cannot reliably use app flows without manual API key wiring.
2. Provider screen is mock-driven:
   - `apps/web/src/features/providers/api/providerSettingsAdapter.ts` is a local in-memory adapter.
   - Result: provider actions are not live and not trustworthy for demo/users.
3. No live provider test UX:
   - There is no explicit backend endpoint + frontend button for connection verification.

## 3) Scope (KISS)

In scope:
1. Session-authenticated runtime path for web app.
2. Live provider settings integration (list/connect/disconnect/reauth).
3. Provider "Test connection" endpoint + UI button + result state.
4. Local demo bootstrap path for first tenant user.
5. E2E smoke test for login -> provider test -> dashboard access.

Out of scope:
1. Scheduling epics (E6).
2. Full observability expansion (E7) beyond request-id display and smoke logs.
3. Performance/accessibility hardening epics (E8) unless blocking.

## 4) Proposed Issues (New)

1. `BE-103` (P0): Add session auth support for tenant runtime endpoints (`/v1/*`) used by web app.
2. `BE-104` (P0): Add provider live test endpoint `POST /v1/providers/{provider_id}/test-connection`.
3. `BE-105` (P1): Add first-user bootstrap endpoint (control-plane only) for tenant admin user creation.
4. `FE-204` (P0): Replace local provider adapter with real API integration.
5. `FE-205` (P0): Add provider test-connection button + status panel (success/failure + timestamp).
6. `FE-106` (P0): Remove static API-key dependency from frontend runtime flow; bind API auth to session.
7. `QA-201` (P0): Add web smoke E2E: login, providers load, provider test action visible, dashboard fetch.

## 5) Use Existing Open Issues (Near-Term)

Pull into this MVP where relevant:
1. `#16` FE-202 provider health/sync metadata.
2. `#17` FE-203 provider flow tests.
3. `#12` FE-104 auth test coverage.
4. `#10` FE-102 role-aware UX (minimal role guard only, if needed for admin-only actions).

## 6) Priority Order

P0 (must ship for next MVP demo):
1. BE-103
2. FE-106
3. FE-204
4. BE-104
5. FE-205
6. QA-201

P1 (immediately after P0 if capacity remains):
1. BE-105
2. FE-202 (#16)
3. FE-203 (#17)
4. FE-104 (#12)

## 7) Parallel Execution Flows

## Flow A: Auth Runtime Alignment (BE1 + FE1 + QA1)

- BE1 (Nebula): implement BE-103.
- FE1 (Orion): implement FE-106 against BE-103 contract.
- QA1 (Apollo): add and run auth/runtime smoke checks (QA-201 partial).

Dependency:
- FE1 starts with API contract draft + mock, finalizes after BE1 merge.

## Flow B: Provider Live Usability (BE2 + FE2 + QA1)

- BE2 (Andromeda): implement BE-104 test-connection endpoint.
- FE2 (Vega): implement FE-204 + FE-205.
- QA1 (Apollo): provider live-flow integration tests + failure-path checks.

Dependency:
- FE2 can build UI now; wire final request/response mapping after BE2 endpoint lands.

## Flow C: Onboarding / Bootstrap (BE1 + QA1)

- BE1: BE-105 first-user bootstrap endpoint (control-plane protected).
- QA1: add runbook steps + API negative tests.

Dependency:
- Independent; can run in parallel with A/B.

## 8) Acceptance Criteria for This MVP

1. User logs in from web UI without preconfigured static `VITE_API_KEY`.
2. After login, dashboard and provider pages load using session-authenticated runtime access.
3. Provider page includes `Test connection` action per provider.
4. Test connection returns clear result (`connected` / `error`) and updates UI metadata.
5. One automated E2E smoke test validates happy path.
6. Updated runbook demonstrates setup and flow in <= 10 minutes.

## 9) Delivery Sequence (Suggested 5-Day Sprint)

Day 1:
1. Freeze API contracts for BE-103 and BE-104.
2. FE scaffolds for session-bound auth + provider test UI states.

Day 2:
1. BE-103 implementation + tests.
2. FE wiring for session auth path.

Day 3:
1. BE-104 implementation + tests.
2. FE provider live adapter integration.

Day 4:
1. QA e2e smoke + edge cases.
2. Runbook refresh and bug fixes.

Day 5:
1. Buffer for regressions.
2. Demo rehearsal and sign-off.

## 10) Immediate Technical Recommendation

Preferred security direction:
1. Use tenant user session auth directly for web runtime APIs.
2. Avoid issuing long-lived API keys to browser clients.

Fallback (if kept temporarily):
1. Mint short-lived session-bound API key after login, with strict TTL and revocation on logout.
