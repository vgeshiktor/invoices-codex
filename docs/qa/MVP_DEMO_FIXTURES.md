# MVP Demo Fixtures (QA-201)

Date: 2026-03-17  
Owner: QA (Apollo)  
Issue: #82

## Fixture Intent

These fixtures keep MVP smoke execution deterministic while BE-103/BE-104/FE-204/FE-205 are landing in parallel.

## Primary Test Identities

- Tenant:
- `id`: `ten-mvp-smoke-1`
- `slug`: `acme`
- `name`: `Acme Ltd`
- User:
- `id`: `usr-mvp-smoke-1`
- `email`: `ops@acme.test`
- `role`: `admin`
- Session:
- `session_id`: `ses-mvp-smoke-1`
- `access_token`: `mvp-access-token`

## Provider Fixture Data

- Gmail provider:
- `id`: `prov-gmail-1`
- `provider_type`: `gmail`
- `connection_status`: `connected`
- Outlook provider:
- `id`: `prov-outlook-1`
- `provider_type`: `outlook`
- `connection_status`: `disconnected`

## Stubbed API Responses Used By Smoke

- `POST /auth/login`:
- Success payload with tenant/user/session and bearer token.
- Failure payload with `AUTH_INVALID_CREDENTIALS`.
- `GET /v1/providers`:
- Returns two provider rows (gmail + outlook) for deterministic provider page rendering.
- `POST /v1/providers/{provider_id}/test-connection`:
- Returns `provider`, `status`, `message`, `tested_at`, and `request_id`.
- `GET /v1/dashboard/summary`:
- Returns minimal summary object to validate dashboard request success path.

## Notes

- The fixture contract for `test-connection` is intentionally aligned with the final BE-104 + FE-205 response/rendering path.
- The smoke test now asserts the rendered success panel rather than a temporary skip guard.
