# Collection Jobs Runtime Contract (Week 4/5)

Issues: `BE-201`, `BE-202`
Status: Backend contract for collection run lifecycle and orchestration.

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
- Initial create enqueues an async collection orchestration task and sets `queue_job_id`.

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

Execution emits:

- `collection_job.run.started`
- `collection_job.run.succeeded`
- `collection_job.run.failed`

## 6. Orchestration Semantics (BE-202)

Collection orchestration worker behavior:

1. Marks job `running` and sets `started_at`.
2. For each requested provider:
   - validates provider configuration exists and is connected.
   - executes provider collector.
   - persists discovered/downloaded files into SaaS storage + `saas_invoice_files`.
3. Creates parse jobs linked to collected files and enqueues parse tasks.
4. Persists:
   - `files_discovered`
   - `files_downloaded`
   - `parse_job_ids`
5. Finalizes job status:
   - `succeeded` when all providers complete without failures.
   - `failed` when any provider fails or no files are downloaded.
6. Failure details are serialized in `error_message` as a UI-safe JSON payload.

## 7. FE Compatibility Notes

- Provider settings flows are unchanged for `Connect`, `Disconnect`, and `Re-auth`.
- Supported provider types remain `'gmail'` and `'outlook'`.
- Collection execution requires provider state `'connected'`; providers in `'disconnected'` or `'error'` state fail with a structured provider failure.
- Initial API response status remains `'queued'` before worker execution starts.
- FE copy alignment: use `Run started` when queue submission succeeds.
- FE-201 failure-path behavior remains: `renders a recoverable action error when connect fails`.
- Collection wizard failure-path expectation remains: `shows error state when submit request fails`.
