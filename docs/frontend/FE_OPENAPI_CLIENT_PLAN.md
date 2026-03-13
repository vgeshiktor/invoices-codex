# FE OpenAPI Client Plan (`FE-004`)

Prepared by: Vega (FE2)
Prepared on: 2026-03-11
Scope lock: Day 0 prep for Week 1 (`FE-004`)
Constraint: spec only on Day 0. Do not run generation yet.

## 1. Objective

Define the exact OpenAPI client generation command, output layout, and usage conventions for `apps/web` (Vite + TypeScript).

## 2. Inputs and Constraints

- OpenAPI source: `integrations/openapi/saas-openapi.v0.1.0.json`
- OpenAPI version: `3.1.0`
- Schema currently has no `servers` block, so base URL must come from frontend env.
- Security schemes in schema:
  - `ApiKeyAuth` via `X-API-Key`
  - `ControlPlaneKeyAuth` via `X-Control-Plane-Key`

## 3. Tooling Decision (Week 1)

Use `@hey-api/openapi-ts` with fetch client output.

Rationale:
- Works cleanly with Vite/TypeScript and browser fetch.
- Generates typed models + service methods from one command.
- Keeps runtime lightweight compared with larger generator stacks.

Planned `apps/web` dev dependency:
- `@hey-api/openapi-ts`

## 4. Exact Generation Command Contract

Run from repo root:

```bash
cd apps/web
npx @hey-api/openapi-ts \
  -i ../../integrations/openapi/saas-openapi.v0.1.0.json \
  -o src/shared/api/generated \
  -c @hey-api/client-fetch
```

Planned `package.json` script (Week 1 implementation):

```json
{
  "scripts": {
    "api:generate": "openapi-ts -i ../../integrations/openapi/saas-openapi.v0.1.0.json -o src/shared/api/generated -c @hey-api/client-fetch"
  }
}
```

## 5. Generated Output and Ownership

Planned output directory:
- `apps/web/src/shared/api/generated/`

Rules:
- Generated directory is machine-owned (no manual edits).
- Regeneration happens only by running `npm run api:generate`.
- Any custom logic lives outside generated files.

## 6. Typed Client Usage Conventions

## 6.1 Layering

- `src/shared/api/generated/*`: generated types/services only.
- `src/shared/api/client.ts`: runtime wrapper (base URL, headers, error mapping).
- `src/features/*/api/*.ts`: feature-level API adapters using generated services.
- UI components must not call generated services directly.

## 6.2 Base URL and transport

- Resolve API base URL from `import.meta.env.VITE_API_BASE_URL`.
- Normalize once at app startup (remove trailing slash).
- Pass normalized base URL into generated client config.

## 6.3 Auth/header policy

- Primary tenant requests: inject `X-API-Key` only when key exists.
- Control-plane flows (admin-only): inject `X-Control-Plane-Key` only in dedicated adapters.
- Never hardcode keys in source; read from runtime env or auth/session state.

## 6.4 Error handling

- Convert generated/network errors into one frontend `ApiError` shape in `client.ts`.
- Preserve status code + request id (if present) for UI and diagnostics.
- Keep raw server payload attached for debug logs only.

## 6.5 Operation usage

- Prefer operation-level functions from generated client.
- Keep one adapter per feature domain (`dashboard`, `files`, `parse-jobs`, `reports`, etc.).
- Do not re-export entire generated namespace from feature code; export only needed methods/types.

## 7. Week 1 Implementation Checklist (`FE-004`)

1. Add `@hey-api/openapi-ts` to `apps/web` dev dependencies.
2. Add `api:generate` script exactly as defined.
3. Run generation once in Week 1 and commit generated output.
4. Add `src/shared/api/client.ts` wrapper and wire base URL from env.
5. Integrate one thin typed usage path (for example `GET /v1/dashboard/summary`).
6. Add CI check to fail if generated client is out of date.

## 8. Risks and Controls

- Risk: schema churn changes generated signatures.
  - Control: pin input to committed snapshot `saas-openapi.v0.1.0.json` during Week 1.
- Risk: exposing API keys in browser.
  - Control: local-only keys via `.env.local`; production auth migration in Week 2.
- Risk: developers editing generated files.
  - Control: document machine-owned folder rule + regenerate-only workflow.

## 9. Script and CI Contract (Implementation-Ready)

Recommended Week 1 scripts in `apps/web/package.json`:

```json
{
  "scripts": {
    "api:generate": "openapi-ts -i ../../integrations/openapi/saas-openapi.v0.1.0.json -o src/shared/api/generated -c @hey-api/client-fetch",
    "api:check": "npm run api:generate && ./scripts/check-api-drift.sh"
  }
}
```

`apps/web/scripts/check-api-drift.sh` is the single drift-check implementation and fails on both tracked and untracked generated changes.

CI usage (Week 1 / `FE-007`):

```bash
cd apps/web
npm run api:check
```

Behavior:
- CI fails when generated artifacts differ from committed output.
- Prevents silent drift between schema and frontend client.

## 10. Endpoint-Specific Note from Current Spec

`POST /v1/files` uses multipart file payload (`multipart/form-data`).

Implementation convention:
- Keep upload call in a dedicated adapter (`features/files/api/upload.ts`).
- Adapter handles `File` -> request body mapping and explicit Content-Type handling.
- Do not spread upload payload construction into UI components.

## 11. Endpoint and Header Ownership Matrix (Current Contract)

Use this mapping to keep adapter boundaries explicit in Week 1.

| Endpoint group | Example routes | Security | Header policy | Planned adapter area |
|---|---|---|---|---|
| Health | `GET /healthz` | none | no auth header | `shared/api/health` |
| Tenant API | `/v1/dashboard/summary`, `/v1/files`, `/v1/parse-jobs`, `/v1/reports`, `/v1/invoices` | `ApiKeyAuth` | `X-API-Key` when configured | `features/*/api/*` |
| Admin API keys | `/v1/admin/api-keys*` | `ApiKeyAuth` | `X-API-Key` only | `features/admin/api/*` |
| Control plane | `/v1/control-plane/tenants` | `ControlPlaneKeyAuth` | `X-Control-Plane-Key` only in control-plane adapter | `features/control-plane/api/*` |

Convention:
- Do not mix tenant and control-plane calls in one adapter module.
- Keep header logic centralized in `src/shared/api/client.ts` and/or adapter-specific request hooks.

## 12. FE-004 Day 1 Done Criteria

`FE-004` should be considered done when all are true:

1. `api:generate` and `api:check` scripts exist and run successfully.
2. Generated output is committed under `src/shared/api/generated`.
3. Shared client wrapper consumes typed env config and injects only required headers.
4. At least one production route uses generated types + operation function end-to-end.
5. CI executes stale-generation guard (`npm run api:check`) in required checks.
