# Auth Runtime Integration Notes (Day 0)

Date: 2026-03-11
Owners: BE1 (contract/API), BE2 (runtime integration)

Canonical contract source:
- Error codes and status mapping: this file, section `3`.
- Auth audit event taxonomy and payload keys: this file, section `5.1`.
- `AUTH_EDGE_CASE_CHECKLIST.md` is a verification artifact and must reference these canonical sections.

## 1. Current Auth-Adjacent Runtime Behavior

This is the current baseline in `apps/workers-py/src/invplatform/saas`:

- Runtime auth is API-key based (`X-API-Key`) on `/v1/*`.
- Tenant resolution is done in dependency `get_tenant_id` (`api.py`), which:
  - returns `401 missing API key` when header is absent.
  - returns `401 invalid API key` when key cannot be resolved or is revoked.
- API key revocation is immediate: `auth.resolve_tenant_id_from_api_key` rejects revoked keys (`auth.py`).
- Request middleware always sets/returns `X-Request-ID` and captures metrics.
- Request middleware writes `api.*` audit events only when tenant can be resolved before handler execution.
- Tenant isolation is enforced by SQLAlchemy guard + explicit tenant repository filters (`db.py`, `repository.py`).
- Control plane auth is separate (`X-Control-Plane-Key`) and should remain independent from tenant user sessions.

## 2. Integration Points For New User Sessions (Week 2)

## 2.1 API Dependency Layer (Primary Hook)

Current protected routes depend on `get_tenant_id`.
Week 2 should introduce a unified resolver, e.g. `get_auth_context`, returning:

- `tenant_id`
- `subject_type` (`user` or `api_key`)
- `subject_id` (user id or api key id/prefix)
- `roles` (for user sessions)
- `session_id` (nullable for API key requests)

Implementation note:
- Keep `get_tenant_id` as compatibility wrapper (`return context.tenant_id`) while migrating routes.
- This minimizes route churn and supports phased rollout.

## 2.2 Request Middleware (Audit + Request ID)

Current middleware tries to resolve tenant only via `X-API-Key` before `call_next`.
For session auth, add one of:

- Option A: middleware reads auth context populated by dependency (post-handler hook), or
- Option B: middleware resolves session/cookie token directly (preferred for complete auth-failure audit coverage).

Required Week 2 outcome:
- `X-Request-ID` returned for all auth responses (`200/401/403`).
- Auth failures emit auditable events (`auth.login_failed`, `auth.refresh_failed`, `auth.access_denied`) with request id.

## 2.3 Service/Model Layer

Add session-aware service APIs without changing existing API-key service paths:

- `authenticate_user(...)`
- `create_session(...)`
- `refresh_session(...)`
- `revoke_session(...)`
- `get_current_user(...)`

Data model additions expected by Week 2:

- tenant user entity (or mapped identity reference)
- session table with expiry/revocation metadata
- refresh token family/versioning (to prevent replay after rotation/logout)

## 2.4 Tenant Safety Integration

Tenant must be derived from trusted server-side session state, not only client-sent tenant identifiers.

- `/auth/login` must validate user-to-tenant binding.
- `/v1/me` must return tenant id from active session.
- For hybrid mode, if both API key and session are present and tenant ids differ, reject with `403`.

## 2.5 Compatibility With Existing Integrations

Existing machine clients and internal scripts use API keys today.

- Keep API-key auth active during Week 2 for non-browser clients.
- Do not change control-plane key behavior.
- Restrict session requirement rollout to frontend-facing flows first.

## 2.6 Endpoint Integration Map (Week 2 Contract Target)

- `POST /auth/login`
  - Input: tenant identifier + user credentials (exact tenant selector field to be finalized by BE1).
  - Runtime hooks: `authenticate_user` -> `create_session`.
  - Audit: `auth.login_succeeded` or `auth.login_failed` with request id.
- `POST /auth/refresh`
  - Input: refresh credential from secure session transport.
  - Runtime hooks: `refresh_session` with rotation/replay detection.
  - Audit: `auth.refresh_succeeded` or `auth.refresh_failed`.
- `POST /auth/logout`
  - Input: active session context.
  - Runtime hooks: `revoke_session` (idempotent).
  - Audit: `auth.logout`.
- `GET /v1/me`
  - Input: active session context.
  - Runtime hooks: `get_current_user`.
  - Output: `user_id`, `tenant_id`, `roles`, `session_expires_at`.

## 2.7 Auth Context Contract (Runtime Internal)

Suggested internal shape returned by `get_auth_context`:

```json
{
  "tenant_id": "string",
  "subject_type": "user|api_key|anonymous",
  "subject_id": "string|null",
  "roles": ["string"],
  "session_id": "string|null",
  "auth_mode": "session|api_key",
  "credential_status": "valid|expired|revoked|invalid"
}
```

Notes:

- `tenant_id` must be server-derived from validated credentials.
- `subject_id` should not expose raw secret material (never token value).
- `credential_status` is internal-only but useful for reason-code mapping and observability.
- `subject_type=anonymous` is expected only when no valid principal is established
  (for example: missing credentials, invalid login attempt before user resolution, or public endpoints).

## 3. Error Contract (Implementation-Ready)

Minimum expected behavior for Week 2:

- `401` for missing/expired/invalid session.
- `403` for authenticated user lacking tenant access or role permission.
- `200` logout should be idempotent even if session already invalidated.
- All auth endpoint responses include `X-Request-ID`.

Recommended stable error payload fields:

- `code` (machine-readable; e.g. `SESSION_EXPIRED`, `TENANT_MISMATCH`, `CREDENTIAL_REVOKED`)
- `message`
- `request_id`

Recommended auth error code set (freeze on Day 1):

- `AUTH_REQUIRED`
- `SESSION_INVALID`
- `SESSION_EXPIRED`
- `TENANT_MISMATCH`
- `ACCESS_DENIED`
- `CREDENTIAL_REVOKED`
- `TOKEN_REPLAY_DETECTED`

Standard error payload example:

```json
{
  "code": "SESSION_EXPIRED",
  "message": "Session has expired. Please log in again.",
  "request_id": "req-123"
}
```

Default status mapping:

- `AUTH_REQUIRED`, `SESSION_INVALID`, `SESSION_EXPIRED`, `CREDENTIAL_REVOKED`, `TOKEN_REPLAY_DETECTED` -> `401`
- `TENANT_MISMATCH`, `ACCESS_DENIED` -> `403`

## 3.1 Endpoint Payload Drafts (Freeze Candidate)

`POST /auth/login` request:

```json
{
  "tenant": "acme",
  "email": "user@example.com",
  "password": "********"
}
```

`POST /auth/login` `200` response:

```json
{
  "user_id": "usr_123",
  "tenant_id": "t_123",
  "roles": ["owner"],
  "session_expires_at": "2026-03-23T11:30:00Z"
}
```

`POST /auth/refresh` `200` response:

```json
{
  "user_id": "usr_123",
  "tenant_id": "t_123",
  "roles": ["owner"],
  "session_expires_at": "2026-03-23T12:30:00Z"
}
```

`POST /auth/logout` `200` response:

```json
{
  "ok": true
}
```

`GET /v1/me` `200` response:

```json
{
  "user_id": "usr_123",
  "tenant_id": "t_123",
  "roles": ["owner"],
  "session_expires_at": "2026-03-23T12:30:00Z"
}
```

## 4. Safe Rollout Strategy (Phased + Flagged)

Use explicit runtime flags in `ApiAppConfig` (or env-backed equivalent):

- `auth_sessions_enabled` (default `false`)
- `auth_mode` (`api_key_only` | `hybrid` | `session_required`, default `api_key_only`)
- `audit_auth_failures_enabled` (default `true`)

`auth_mode` credential precedence and tie-break rule (must be deterministic):

1. `api_key_only`
   - Require valid API key for protected `/v1/*`.
   - Ignore session credentials if present.
   - Auth context resolves as `subject_type=api_key`.
2. `session_required`
   - Require valid user session for protected `/v1/*`.
   - Ignore API key credentials if present.
   - Auth context resolves as `subject_type=user`.
3. `hybrid`
   - If both session and API key are present, validate both.
   - If either credential is invalid/revoked/expired: return `401`.
   - If both are valid but map to different tenants: return `403 TENANT_MISMATCH`.
   - If both are valid and same tenant: session takes precedence (`subject_type=user`).
   - If only one credential is present and valid: use that credential type.
   - If neither credential is valid/present: return `401 AUTH_REQUIRED`.

Phases:

1. Phase 0: `api_key_only`
   - Ship `/auth/login`, `/auth/refresh`, `/auth/logout`, `/v1/me`.
   - Existing `/v1/*` dependencies unchanged.
2. Phase 1: `hybrid`
   - Frontend uses sessions; API-key fallback still allowed for existing clients.
   - Tenant mismatch detection enabled when dual credentials are present.
3. Phase 2: `session_required` (frontend routes first)
   - Require session on selected route groups.
   - Keep API-key-only paths for machine integrations until migration is complete.

Release gate before entering Phase 2:

- passing tests for expired session, multi-tab logout, tenant mismatch, revoked credentials.
- audit event coverage validated for auth success/failure with request id correlation.

Recommended route policy for phased endpoints:

- Always session-capable: `/auth/login`, `/auth/refresh`, `/auth/logout`, `/v1/me`
- Hybrid-allowed during migration: existing `/v1/*` business endpoints
- Never session-bound: `/v1/control-plane/*` (control-plane key only)

## 5. Open Decisions For Day 1 (BE1 + BE2)

- Final session transport: secure HttpOnly cookies vs bearer tokens (recommend cookies for web).
- Session lifetime and refresh rotation policy (absolute + idle timeout values).
- Canonical list of auth audit event names and payload keys.
- Whether auth-failure events with unknown tenant go to global/system audit stream.

## 5.1 Auth Audit Event Taxonomy (Freeze Candidate)

| Event | Outcome | Typical Status | Required `reason_code` |
| --- | --- | --- | --- |
| `auth.login_succeeded` | success | `200` | no |
| `auth.login_failed` | failure | `401` or `403` | yes |
| `auth.refresh_succeeded` | success | `200` | no |
| `auth.refresh_failed` | failure | `401` | yes |
| `auth.logout` | success | `200` | no |
| `auth.access_denied` | failure | `401` or `403` | yes |
| `auth.session_expired` | failure | `401` | yes |

Mandatory payload keys for all auth events:

- `request_id`
- `outcome`
- `tenant_id` (nullable only for unknown-tenant failures)
- `subject_type`
- `subject_id` (nullable for anonymous failures)
- `endpoint`
- `status_code`
- `reason_code` (required only for failures)

## 6. Implementation Handoff Sequence (Day 1 Start)

1. BE1 freezes endpoint request/response/error schemas and DB migration scope.
2. BE2 wires `get_auth_context` + middleware audit/request-id integration.
3. BE1/BE2 add integration tests for 401/403 + request-id + audit payload presence.
4. FE starts against frozen `/auth/*` and `/v1/me` contract in hybrid mode.
