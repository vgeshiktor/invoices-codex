# Provider Runtime Contract (Week 3)

Issue: `BE-101`
Status: Draft for implementation parity between backend and frontend.

## 1. Scope

This contract defines tenant-scoped provider configuration CRUD for:

- `GET /v1/providers`
- `POST /v1/providers`
- `PATCH /v1/providers/{provider_id}`
- `DELETE /v1/providers/{provider_id}`

OAuth lifecycle endpoints are out of scope for `BE-101` and are handled by `BE-102`.

## 2. Provider Entity

Provider records are persisted in `saas_provider_configs` and are tenant-owned.

Fields returned by API:

- `id` (string UUID)
- `tenant_id` (string UUID)
- `provider_type` (`gmail` | `outlook`)
- `display_name` (nullable string)
- `connection_status` (`connected` | `disconnected` | `error`)
- `token_expires_at` (nullable ISO datetime)
- `last_successful_sync_at` (nullable ISO datetime)
- `last_error_code` (nullable string)
- `last_error_message` (nullable string)
- `created_at` (ISO datetime)
- `updated_at` (ISO datetime)

Tenant uniqueness rule:

- `(tenant_id, provider_type)` must be unique.

## 3. Request/Response Shapes

### 3.1 `GET /v1/providers`

Response:

```json
{
  "items": [],
  "total": 0
}
```

### 3.2 `POST /v1/providers`

Request:

```json
{
  "provider_type": "gmail",
  "display_name": "Finance Gmail"
}
```

Response: provider object (status `201`).

Validation:

- `provider_type` must be `gmail` or `outlook`.
- Duplicate provider type for the same tenant returns `400`.

### 3.3 `PATCH /v1/providers/{provider_id}`

Request supports partial updates for:

- `display_name`
- `connection_status`
- `token_expires_at`
- `last_successful_sync_at`
- `last_error_code`
- `last_error_message`

Response: provider object (status `200`).

Validation:

- At least one field is required.
- Unknown fields return `400`.
- Unknown `provider_id` in tenant scope returns `404`.

### 3.4 `DELETE /v1/providers/{provider_id}`

Response: status `204` with empty body.

Validation:

- Unknown `provider_id` in tenant scope returns `404`.

## 4. Security & Isolation

- All endpoints require `X-API-Key`.
- Tenant is resolved from API key and enforced on every read/write.
- Cross-tenant reads/updates/deletes return `404` for provider IDs that are not visible in caller tenant.
- Provider secrets are not returned by these APIs.

## 5. Audit Events

Tenant audit events emitted by backend:

- `provider.create`
- `provider.update`
- `provider.delete`

Each event payload includes `provider_id` and operation-specific metadata.
