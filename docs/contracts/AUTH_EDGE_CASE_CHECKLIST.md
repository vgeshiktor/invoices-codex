# Auth Edge-Case Checklist (Week 2)

Date: 2026-03-11
Scope: `BE-001` runtime expectations for `/auth/login`, `/auth/refresh`, `/auth/logout`, `/v1/me`

Canonical reference for contract values:

- Error codes and status mapping: `AUTH_RUNTIME_INTEGRATION_NOTES.md` section `3`.
- Auth audit event taxonomy and payload keys: `AUTH_RUNTIME_INTEGRATION_NOTES.md` section `5.1`.
- If this checklist conflicts with the integration notes, the integration notes are canonical.

## 1. Expired/Invalid Session

- [ ] `GET /v1/me` with expired session returns `401`.
- [ ] `GET /v1/me` with malformed/unknown token returns `401`.
- [ ] Response body includes stable error code (`SESSION_EXPIRED` or `SESSION_INVALID`).
- [ ] Response includes `X-Request-ID`.
- [ ] Audit event written: `auth.access_denied` or `auth.session_expired`.
- [ ] Frontend behavior verified: redirect to login and clear cached auth state.
- [ ] Refresh endpoint behavior verified:
  - expired refresh token -> `401` + no new session.
  - rotated/replayed refresh token -> `401` and revoke token family.

## 2. Multi-Tab Logout

- [ ] `POST /auth/logout` invalidates current session immediately.
- [ ] Idempotency: repeated logout returns `200` (safe no-op).
- [ ] Other browser tabs receive logout signal and stop calling protected APIs with stale session.
- [ ] Next protected call from other tab returns `401`.
- [ ] Audit events include:
  - `auth.logout` (initiating tab)
  - `auth.access_denied` (subsequent stale-tab call)
- [ ] FE test coverage includes at least one multi-tab simulation (BroadcastChannel/storage-event strategy).

## 3. Tenant Mismatch

- [ ] Login with user not bound to requested tenant returns `403` (`TENANT_MISMATCH`).
- [ ] If dual credentials are sent (session + API key) with different tenants, request returns `403`.
- [ ] No tenant-scoped data is returned on mismatch path.
- [ ] Audit event includes mismatch metadata (safe fields only):
  - requested tenant id / resolved tenant id
  - subject id
  - request id

## 4. Revoked Credentials

- [ ] Revoked API key immediately fails with `401` on next request (already true in current runtime, must remain true).
- [ ] Revoked user session/refresh token fails with `401` on next request.
- [ ] Refresh-token replay detection revokes active token family and forces re-login.
- [ ] Audit event emitted with explicit reason:
  - `CREDENTIAL_REVOKED` or `TOKEN_REPLAY_DETECTED`.
- [ ] Rotation/revocation operations are auditable with actor attribution when available.

## 5. Request-ID and Audit Event Handling

- [ ] Every auth endpoint response (`success` and `error`) includes `X-Request-ID`.
- [ ] Incoming `X-Request-ID` is echoed back; missing value is generated server-side.
- [ ] Auth success events include request id, tenant id, subject id, outcome.
- [ ] Auth failure events include request id and failure reason; avoid sensitive data in payload.
- [ ] Middleware/service failure to persist audit event does not crash request handling, but emits error log/metric.
- [ ] Event naming is standardized and versioned (single source list in contract doc).

Required auth audit payload keys (minimum):

- [ ] `request_id`
- [ ] `event_type`
- [ ] `outcome` (`success` | `failure`)
- [ ] `tenant_id` (nullable only when unknown at failure time)
- [ ] `subject_type` (`user` | `api_key` | `anonymous`)
- [ ] `subject_id` (nullable for anonymous failures)
- [ ] `reason_code` (required on failures)

Clarification:
- Use `subject_type=anonymous` for requests where no valid principal is established
  (for example `AUTH_REQUIRED` or invalid login attempts before user resolution).

## 6. Verification Matrix (Minimum Tests)

- [ ] Unit:
  - session expiry evaluator
  - refresh rotation/replay logic
  - tenant binding validation
- [ ] Integration:
  - login success/failure by tenant
  - refresh happy/expired/replayed
  - logout idempotency + post-logout access denial
- [ ] E2E:
  - login -> protected route -> logout -> redirected to login
  - expired session auto-redirect flow
  - role/tenant denial path with clear UX

## 7. Rollout Evidence Gates

- [ ] Hybrid mode smoke test: API-key client still works on at least one protected `/v1/*` endpoint.
- [ ] Session mode smoke test: frontend auth journey works end-to-end with `/v1/me`.
- [ ] Audit sampling confirms request-id correlation on `login`, `refresh`, `logout`, and denied access.
- [ ] No P0/P1 defects on listed edge cases.

## 8. Exit Criteria To Start Week 2 Coding

- [ ] Error code catalog finalized for `401/403` auth failures.
- [ ] Audit event taxonomy for auth actions approved.
- [ ] Rollout mode chosen (`api_key_only` -> `hybrid` plan confirmed).
- [ ] BE1/BE2 agree on session transport and token lifetime policy.

## 9. Scenario Matrix (Implementation-Ready)

| ID | Scenario | Endpoint | Expected Status | Expected `code` | Expected Audit Event |
| --- | --- | --- | --- | --- | --- |
| `AUTH-EC-01` | Expired session token | `GET /v1/me` | `401` | `SESSION_EXPIRED` | `auth.session_expired` |
| `AUTH-EC-02` | Invalid/malformed token | `GET /v1/me` | `401` | `SESSION_INVALID` | `auth.access_denied` |
| `AUTH-EC-03` | Refresh replayed token | `POST /auth/refresh` | `401` | `TOKEN_REPLAY_DETECTED` | `auth.refresh_failed` |
| `AUTH-EC-04` | Repeat logout | `POST /auth/logout` | `200` | n/a | `auth.logout` |
| `AUTH-EC-05` | Tenant mismatch at login | `POST /auth/login` | `403` | `TENANT_MISMATCH` | `auth.login_failed` |
| `AUTH-EC-06` | Session/API-key tenant mismatch | protected `/v1/*` | `403` | `TENANT_MISMATCH` | `auth.access_denied` |
| `AUTH-EC-07` | Revoked API key access | protected `/v1/*` | `401` | `CREDENTIAL_REVOKED` | `auth.access_denied` |
| `AUTH-EC-08` | Revoked session access | protected `/v1/*` | `401` | `CREDENTIAL_REVOKED` | `auth.access_denied` |
| `AUTH-EC-09` | Missing credentials on protected route | protected `/v1/*` | `401` | `AUTH_REQUIRED` | `auth.access_denied` |

## 10. Ownership Split (Day 1 Preparation)

- BE1: freeze endpoint payloads, status/code mapping, and migration DDL.
- BE2: middleware/request-id/audit integration behavior and auth-context resolver wiring plan.
- FE1/FE2: multi-tab logout propagation strategy + denied-session UX copy.
- QA1: test-case skeletons for `AUTH-EC-01..08` in integration + e2e suites.
