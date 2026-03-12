# Provider Week 3 Contract (BE-101)

Status: Draft frozen for BE-101 implementation
Date: 2026-03-11

Scope:
- tenant-scoped provider configuration CRUD only.
- OAuth start/callback/refresh/revoke flows are out of scope for BE-101 and covered by BE-102.

## Endpoints

### `GET /v1/providers`

Query params:
- `limit` (int, default `100`, min `1`, max `1000`)
- `offset` (int, default `0`, min `0`)

Response `200`:

```json
{
  "items": [
    {
      "id": "uuid",
      "tenant_id": "uuid",
      "provider_type": "gmail",
      "display_name": "Ops Gmail",
      "connection_status": "disconnected",
      "config": {},
      "token_expires_at": null,
      "last_successful_sync_at": null,
      "last_error_code": null,
      "last_error_message": null,
      "created_at": "2026-03-11T21:00:00+00:00",
      "updated_at": "2026-03-11T21:00:00+00:00"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

### `POST /v1/providers`

Request body:

```json
{
  "provider_type": "gmail",
  "display_name": "Ops Gmail",
  "connection_status": "disconnected",
  "config": {"sync_window_days": 30}
}
```

Response:
- `201` provider object (same shape as `GET` item)
- `400` validation error (`provider_type`, `connection_status`, `config`)
- `409` provider for the same tenant + `provider_type` already exists

### `PATCH /v1/providers/{provider_id}`

Partial update body (all fields optional, at least one required):

```json
{
  "display_name": "Finance Gmail",
  "connection_status": "connected",
  "config": {"sync_window_days": 7},
  "token_expires_at": "2030-01-01T00:00:00+00:00",
  "last_successful_sync_at": "2030-01-01T00:00:00+00:00",
  "last_error_code": null,
  "last_error_message": null
}
```

Response:
- `200` updated provider object
- `400` invalid payload or empty patch body
- `404` provider not found in tenant
- `409` unique conflict on tenant + provider type

### `DELETE /v1/providers/{provider_id}`

Response:
- `204` deleted
- `404` provider not found in tenant

## Domain Rules

- Allowed `provider_type`: `gmail`, `outlook`.
- Allowed `connection_status`: `connected`, `disconnected`, `error`.
- Per-tenant uniqueness: one row per `(tenant_id, provider_type)`.
- `config` persists as JSON object (`config_json` at rest).

## Tenant Isolation and Security

- Endpoints are tenant-scoped via `X-API-Key` tenant resolution.
- CRUD operations always filter by `tenant_id`.
- Tenant guard includes provider model to prevent unscoped cross-tenant reads.
- Encrypted token columns exist in schema for later OAuth lifecycle work and are never exposed in API responses.

## Audit Events

- `provider.create`
- `provider.update`
- `provider.delete`

All include tenant ID and request actor (`X-Actor`) when provided.
