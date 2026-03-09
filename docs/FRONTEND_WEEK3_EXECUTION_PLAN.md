# Frontend Week 3 Execution Plan

Date: 2026-03-09
Scope: Execute `BE-101`, `BE-102`, `FE-201..FE-203` from `docs/FRONTEND_CONVERSION_BACKLOG.md`

## 1. Week 3 Goal

By end of Week 3:
- tenant-scoped provider configuration domain exists.
- OAuth lifecycle endpoints exist for Gmail and Outlook.
- frontend provider settings page supports connect/disconnect/re-auth.
- provider health and sync metadata are visible in UI.
- provider flows have automated e2e coverage.

## 2. Team Slots (Fill Names)

- `Owner-BE-Provider`: backend provider configuration lead
- `Owner-BE-OAuth`: backend OAuth lifecycle lead
- `Owner-FE-Provider`: frontend provider settings lead
- `Owner-QA`: provider flow test automation lead
- `Owner-Review`: cross-stack reviewer and merge gate

## 3. Issue Map (Week 3 Only)

| ID | Title | Primary Owner | Backup Owner | Depends On |
|---|---|---|---|---|
| BE-101 | Add provider configuration domain and tenant-scoped CRUD APIs | Owner-BE-Provider | Owner-BE-OAuth | BE-001 |
| BE-102 | Implement provider OAuth lifecycle endpoints | Owner-BE-OAuth | Owner-BE-Provider | BE-101 |
| FE-201 | Build provider settings screen (connect/disconnect/re-auth) | Owner-FE-Provider | Owner-Review | BE-102 |
| FE-202 | Show provider health and sync metadata | Owner-FE-Provider | Owner-QA | BE-102 |
| FE-203 | Add provider flow tests for Gmail and Outlook | Owner-QA | Owner-FE-Provider | FE-201 |

## 4. Backend Contract for Week 3 (Freeze Early)

Provider CRUD endpoints (tenant-scoped):
- `GET /v1/providers`
- `POST /v1/providers`
- `PATCH /v1/providers/{provider_id}`
- `DELETE /v1/providers/{provider_id}`

OAuth lifecycle endpoints:
- `POST /v1/providers/{provider_id}/oauth/start`
- `GET /v1/providers/{provider_id}/oauth/callback`
- `POST /v1/providers/{provider_id}/oauth/refresh`
- `POST /v1/providers/{provider_id}/oauth/revoke`

Required provider status fields:
- `provider_type` (`gmail` | `outlook`)
- `connection_status` (`connected` | `disconnected` | `error`)
- `token_expires_at`
- `last_successful_sync_at`
- `last_error_code` / `last_error_message` (nullable)

Security constraints:
- all provider endpoints enforce tenant scoping.
- secrets/tokens are encrypted at rest; never returned in plaintext.
- sensitive state transitions emit audit events with request id.

## 5. Day-by-Day Execution

## Day 1 (Mon): Contract Freeze + Provider Domain

Planned issues:
- BE-101 (start)

Tasks:
1. Freeze provider entity schema and endpoint request/response contracts.
2. Add backend models/migrations for provider configuration.
3. Implement initial provider CRUD (`GET`, `POST`) with tenant isolation tests.

End-of-day checkpoint:
- contract frozen and attached to BE-101.
- backend PR opened with passing CRUD baseline tests.

## Day 2 (Tue): Provider CRUD Complete + OAuth Start

Planned issues:
- BE-101 (finish)
- BE-102 (start)

Tasks:
1. Complete `PATCH`/`DELETE` provider endpoints.
2. Implement OAuth start endpoint for Gmail and Outlook.
3. Define callback state validation and error model.

End-of-day checkpoint:
- BE-101 merged.
- BE-102 in progress with OAuth start implemented.

## Day 3 (Wed): OAuth Callback/Refresh/Revoke + FE Settings Start

Planned issues:
- BE-102 (finish)
- FE-201 (start)

Tasks:
1. Implement OAuth callback/refresh/revoke endpoints.
2. Add provider health fields to provider list response.
3. Build frontend provider settings page and provider cards.

End-of-day checkpoint:
- BE-102 merged.
- FE-201 at least 50% complete.

## Day 4 (Thu): FE Provider UX Completion + Health UX

Planned issues:
- FE-201 (finish)
- FE-202

Tasks:
1. Complete connect/disconnect/re-auth flows in settings page.
2. Render token expiry, last sync, and error state badges.
3. Validate responsive layout for mobile and desktop.

End-of-day checkpoint:
- FE-201 and FE-202 merged.
- manual smoke tests complete for Gmail/Outlook UI states.

## Day 5 (Fri): E2E Provider Flows + Closeout

Planned issues:
- FE-203

Tasks:
1. Add e2e coverage for Gmail and Outlook connect/disconnect/re-auth.
2. Add integration tests for provider status rendering.
3. Stabilize flaky test points and finalize Week 3 report.

End-of-day checkpoint:
- FE-203 merged.
- Week 3 status report posted with PR links and CI links.

## 6. Daily Standup Template

Use this exact format:

- Yesterday: completed IDs
- Today: planned IDs
- Blockers: oauth/provider/frontend/test
- Confidence: `Green | Yellow | Red`

## 7. Definition of Done (Week 3)

For each issue:
- acceptance criteria from issue body met
- tests added and green in CI
- API contract/docs updated where changed
- reviewed and merged

Week-level DoD:
- `BE-101`, `BE-102`, `FE-201`, `FE-202`, `FE-203` all closed
- Gmail and Outlook provider flows are usable from UI
- provider flow e2e tests are required in CI
- no open P0/P1 provider integration defects

## 8. Test Matrix (Minimum)

- Unit:
  - provider status formatting and badge logic
  - oauth state parameter validator helpers
- Integration:
  - provider CRUD happy/error paths
  - OAuth callback success and invalid state handling
  - health metadata rendering in UI
- E2E:
  - Gmail connect -> connected state visible
  - Outlook connect -> connected state visible
  - provider disconnect -> disconnected state visible
  - provider re-auth from error state

## 9. Risks and Fast Mitigations

- Risk: OAuth redirect and callback complexity causes delays.
- Mitigation: implement provider adapters behind a common interface and keep strict callback contract tests.

- Risk: provider token refresh behavior differs between vendors.
- Mitigation: normalize refresh outcome states into a shared status model early.

- Risk: environment misconfiguration blocks local OAuth testing.
- Mitigation: publish provider env checklist and add startup validation errors.

## 10. Week 3 Exit Artifacts

At week close, produce:
1. merged PR list for `BE-101`, `BE-102`, `FE-201..FE-203`.
2. CI links proving provider e2e checks are required and green.
3. short provider integration hardening note before entering Week 4 collection run work.
