# Collection Jobs Runtime Contract (Week 4)

Issue: `BE-201`
Status: Week 4 backend contract for collection run lifecycle.

## 1. Scope

Tenant-scoped collection job endpoints:

- `POST /v1/collection-jobs`
- `GET /v1/collection-jobs`
- `GET /v1/collection-jobs/{collection_job_id}`

## 2. Entity

Collection jobs are persisted in `saas_collection_jobs`.

Lifecycle status values:

- `queued`
- `running`
- `succeeded`
- `failed`

## 3. API Contract

### 3.1 Create

`POST /v1/collection-jobs`

Request:

```json
{
  "providers": ["gmail", "outlook"],
  "month_scope": "2026-04"
}
```

Headers:

- `X-API-Key` (required)
- `Idempotency-Key` (optional, recommended)

Response (`201`):

- `id`
- `tenant_id`
- `status`
- `idempotency_key`
- `providers`
- `month_scope`
- `queue_job_id`
- `started_at`
- `finished_at`
- `files_discovered`
- `files_downloaded`
- `parse_job_ids`
- `error_message`
- `created_at`
- `updated_at`

Validation:

- `providers` must be a non-empty list.
- Allowed providers: `gmail`, `outlook`.
- `month_scope` must match `YYYY-MM`.

Idempotency:

- Same tenant + same `Idempotency-Key` returns existing collection job.

### 3.2 List

`GET /v1/collection-jobs?status=<optional>&limit=<n>&offset=<n>`

Response:

```json
{
  "items": [],
  "total": 0,
  "limit": 100,
  "offset": 0
}
```

### 3.3 Get

`GET /v1/collection-jobs/{collection_job_id}`

Response:

- Collection job object.

Errors:

- `404` when not found in caller tenant scope.

## 4. Security & Isolation

- All endpoints require tenant API key auth.
- Read/write operations are tenant scoped.
- Cross-tenant access returns not found.

## 5. Auditing

Create emits:

- `collection_job.create`

Payload includes:

- `collection_job_id`
- `providers`
- `month_scope`
- `status`
- `idempotency_key`
