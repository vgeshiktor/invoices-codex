# Week 2 Auth Contract (BE-001)

Status: Draft frozen for Week 2 implementation start (Day 0, 2026-03-11).

## Scope

This contract covers only:

- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /v1/me`

Out of scope in Week 2:

- SSO/OIDC providers
- MFA
- user invite/reset-password flows
- replacing existing `X-API-Key` auth for current automation endpoints

## Contract Conventions

- Content type: `application/json` for all request/response bodies.
- Time fields: RFC3339 UTC timestamps.
- Correlation: server echoes or generates `X-Request-ID` on every response.
- Session model:
  - `access_token` is a short-lived bearer token returned in JSON response body.
  - `refresh_token` is an opaque token stored only in `HttpOnly` cookie `inv_refresh`.
  - refresh token rotation occurs on every successful `POST /auth/refresh`.
  - baseline TTLs for Week 2: `access_token=900s`, `refresh_token=30d` (env-configurable).

Refresh cookie attributes:

- `HttpOnly`
- `Secure` (required outside local dev)
- `SameSite=Lax`
- `Path=/auth`
- `Max-Age=<refresh_ttl_seconds>`

## Shared Schemas

### User

```json
{
  "id": "2a1982f2-0d67-4664-a4ca-4fbc9cdd5f1f",
  "email": "ops@acme.test",
  "full_name": "Acme Ops",
  "role": "admin",
  "status": "active"
}
```

### Tenant

```json
{
  "id": "7a4a60e1-f227-45f7-a1e9-5db5f0915b6f",
  "slug": "acme",
  "name": "Acme Ltd"
}
```

### SessionMetadata

```json
{
  "session_id": "3f5d9d75-4f8b-4208-90f1-f4f30290d6dc",
  "access_expires_at": "2026-03-23T08:00:00Z",
  "refresh_expires_at": "2026-04-22T08:00:00Z"
}
```

### Error Model

All `4xx/5xx` responses use:

```json
{
  "error": {
    "code": "AUTH_INVALID_CREDENTIALS",
    "message": "Email or password is incorrect.",
    "request_id": "8f0fbc64-95f3-4a80-9d3f-a4678f9e983f",
    "details": {}
  }
}
```

`details` is optional and endpoint-specific.

## Endpoint Contracts

### `POST /auth/login`

Authenticate a tenant user and create a new session.

Request:

```json
{
  "email": "ops@acme.test",
  "password": "plain-text-password",
  "tenant_slug": "acme"
}
```

Request validation:

- `email`: required, valid email format.
- `password`: required, non-empty.
- `tenant_slug`: required, slug format `[a-z0-9-]{2,64}`.

`200 OK` response:

```json
{
  "access_token": "<jwt-or-signed-token>",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": "2a1982f2-0d67-4664-a4ca-4fbc9cdd5f1f",
    "email": "ops@acme.test",
    "full_name": "Acme Ops",
    "role": "admin",
    "status": "active"
  },
  "tenant": {
    "id": "7a4a60e1-f227-45f7-a1e9-5db5f0915b6f",
    "slug": "acme",
    "name": "Acme Ltd"
  },
  "session": {
    "session_id": "3f5d9d75-4f8b-4208-90f1-f4f30290d6dc",
    "access_expires_at": "2026-03-23T08:00:00Z",
    "refresh_expires_at": "2026-04-22T08:00:00Z"
  }
}
```

Also sets `Set-Cookie: inv_refresh=...`.

Errors:

- `400` `VALIDATION_ERROR`
- `401` `AUTH_INVALID_CREDENTIALS`
- `403` `AUTH_MEMBERSHIP_INACTIVE`
- `429` `AUTH_RATE_LIMITED`

### `POST /auth/refresh`

Rotate refresh token and return a new access token for the same `session_id`.

Request:

- No JSON body required.
- Requires `inv_refresh` cookie.

`200 OK` response:

```json
{
  "access_token": "<jwt-or-signed-token>",
  "token_type": "Bearer",
  "expires_in": 900,
  "session": {
    "session_id": "3f5d9d75-4f8b-4208-90f1-f4f30290d6dc",
    "access_expires_at": "2026-03-23T08:15:00Z",
    "refresh_expires_at": "2026-04-22T08:00:00Z"
  }
}
```

Also sets rotated `Set-Cookie: inv_refresh=...`.

Errors:

- `401` `AUTH_REFRESH_MISSING`
- `401` `AUTH_REFRESH_INVALID`
- `401` `AUTH_SESSION_EXPIRED`
- `401` `AUTH_SESSION_REVOKED`

### `POST /auth/logout`

Revoke the active session tied to `inv_refresh` cookie and clear cookie.

Request:

- No JSON body required.
- Uses `inv_refresh` cookie when present.

`204 No Content` response:

- Always idempotent.
- Returns `Set-Cookie` clearing `inv_refresh`.

Errors:

- none (`204` even if session already revoked or cookie missing)

### `GET /v1/me`

Return current authenticated user + tenant context.

Request headers:

- `Authorization: Bearer <access_token>`

`200 OK` response:

```json
{
  "user": {
    "id": "2a1982f2-0d67-4664-a4ca-4fbc9cdd5f1f",
    "email": "ops@acme.test",
    "full_name": "Acme Ops",
    "role": "admin",
    "status": "active"
  },
  "tenant": {
    "id": "7a4a60e1-f227-45f7-a1e9-5db5f0915b6f",
    "slug": "acme",
    "name": "Acme Ltd"
  },
  "session": {
    "session_id": "3f5d9d75-4f8b-4208-90f1-f4f30290d6dc",
    "access_expires_at": "2026-03-23T08:15:00Z",
    "refresh_expires_at": "2026-04-22T08:00:00Z"
  }
}
```

Errors:

- `401` `AUTH_ACCESS_MISSING`
- `401` `AUTH_ACCESS_INVALID`
- `401` `AUTH_ACCESS_EXPIRED`

## Tenant Isolation Rules (Frozen)

1. Tenant context is derived from authenticated session state only, never from request body/query.
2. `tenant_slug` in login is used only to select membership during authentication.
3. Access token/session must contain a single bound `tenant_id`; all authenticated data access uses this `tenant_id`.
4. Membership checks must pass on login and on each refresh (`active` membership required).
5. `GET /v1/me` must never return cross-tenant data even if user email exists in multiple tenants.
6. Session revocation/logout only affects the current tenant-bound session.

## Audit Event Requirements

All auth endpoints should write audit events with request ID where available:

- `auth.login.succeeded`
- `auth.login.failed`
- `auth.refresh.succeeded`
- `auth.refresh.failed`
- `auth.logout.succeeded`

Minimum payload fields: `request_id`, `tenant_id` (when known), `user_id` (when known), `session_id` (when known), `status_code`.

## Day 0 Freeze Decisions (Canonical)

This document is the source of truth for Week 2 contract behavior where other notes differ.

Frozen choices:

1. `POST /auth/logout` returns `204` (idempotent, no body).
2. Auth audit naming uses dot format (`auth.login.succeeded`, not underscore variants).
3. Access token is returned in response body; refresh token is cookie-only.
4. `tenant_slug` is required at login for membership resolution.

## Open Decisions Blocking Week 2 Start

1. Access token format and signing details (JWT claims/alg/key rotation policy).
2. Refresh replay policy depth (single-session revoke vs token-family revoke).
3. Final hybrid-auth behavior for non-auth `/v1/*` routes when both API key and session are sent.
4. First-user bootstrap path per tenant (control-plane create-user API vs migration seed runbook).

## Suggested Day 1 Implementation Order

1. Add auth schema migration and models (`users`, `memberships`, `sessions`, tenant slug).
2. Implement `POST /auth/login` and `GET /v1/me` happy path with tenant-safe checks.
3. Add shared auth error envelope and `X-Request-ID` propagation on auth routes.
4. Implement `POST /auth/refresh` token rotation and replay handling.
5. Implement idempotent `POST /auth/logout` revocation path and cookie clear.
6. Add tenant isolation and auth edge-case tests (`401`, `403`, refresh replay, logout idempotency).
