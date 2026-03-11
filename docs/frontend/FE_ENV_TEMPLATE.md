# FE Environment Template (Local/Dev/Staging)

Prepared by: Vega (FE2)
Prepared on: 2026-03-11
Scope lock: Day 0 prep for Week 1 (`FE-001`, `FE-004`, `FE-007`)
Constraint: template/spec only on Day 0.

## 1. Objective

Define the frontend env variable contract for Vite + TypeScript across local, dev, and staging environments.

## 2. Vite Env Rules

- Only variables prefixed with `VITE_` are available in browser code.
- Keep secrets out of committed env files.
- Treat `.env.example` as contract documentation only.

## 3. Required Variable Contract

Required for all environments:

- `VITE_API_BASE_URL`
  - Purpose: base URL for generated API client requests.
  - Format: absolute URL (no trailing slash), for example `https://api.dev.example.com`.

Optional (mostly local/dev support):

- `VITE_API_KEY`
  - Purpose: temporary Week 1 API key header for tenant endpoints.
  - Use: local/dev only when auth is not wired yet.
- `VITE_CONTROL_PLANE_KEY`
  - Purpose: temporary key for control-plane endpoints.
  - Use: only for admin/control-plane testing paths.
- `VITE_API_TIMEOUT_MS`
  - Purpose: HTTP timeout override for frontend client wrapper.
  - Default if absent: `15000`.
- `VITE_APP_ENV`
  - Purpose: explicit UI/runtime label (`local`, `development`, `staging`).

## 4. Planned Env File Matrix (`apps/web`)

- `.env.example` -> committed template only
- `.env.local` -> developer machine overrides (gitignored)
- `.env.development` -> shared dev defaults (non-secret)
- `.env.staging` -> staging defaults (non-secret)

## 5. Template Values

`apps/web/.env.example`

```dotenv
# Required
VITE_API_BASE_URL=http://127.0.0.1:8000

# Optional (do not store real secrets in git)
VITE_API_KEY=
VITE_CONTROL_PLANE_KEY=
VITE_API_TIMEOUT_MS=15000
VITE_APP_ENV=local
```

`apps/web/.env.local` (example, not committed)

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_KEY=local_dev_key_placeholder
VITE_CONTROL_PLANE_KEY=
VITE_API_TIMEOUT_MS=15000
VITE_APP_ENV=local
```

`apps/web/.env.development` (example)

```dotenv
VITE_API_BASE_URL=https://api.dev.example.com
VITE_API_KEY=
VITE_CONTROL_PLANE_KEY=
VITE_API_TIMEOUT_MS=15000
VITE_APP_ENV=development
```

`apps/web/.env.staging` (example)

```dotenv
VITE_API_BASE_URL=https://api.staging.example.com
VITE_API_KEY=
VITE_CONTROL_PLANE_KEY=
VITE_API_TIMEOUT_MS=15000
VITE_APP_ENV=staging
```

## 6. API Base URL Strategy

1. Read `VITE_API_BASE_URL` once during app bootstrap.
2. Normalize by trimming trailing slash.
3. Fail fast in development if missing/invalid.
4. Use a single configured base URL for all generated client calls.
5. If control-plane host diverges later, add `VITE_CONTROL_PLANE_BASE_URL` in a backward-compatible update.

## 7. Typed Client Integration Conventions

- Environment parsing lives in one module (`src/shared/config/env.ts`).
- Generated client configuration lives in one module (`src/shared/api/client.ts`).
- Header injection policy:
  - attach `X-API-Key` only when `VITE_API_KEY` is non-empty;
  - attach `X-Control-Plane-Key` only in control-plane adapters.
- All feature APIs consume shared client config; no per-component env access.

## 8. Validation and CI Expectations (Week 1)

- Add startup validation for required env keys in development mode.
- Add one test that fails when `VITE_API_BASE_URL` is missing.
- CI should run without real secrets; only non-secret defaults from template.

## 9. Risks and Mitigations

- Risk: accidental secret commit.
  - Mitigation: keep `.env.local` gitignored and template keys empty.
- Risk: inconsistent base URL formatting.
  - Mitigation: normalize URL in one config utility.
- Risk: temporary API key flow lingering beyond Week 1.
  - Mitigation: mark key usage as transitional and replace with auth token flow in Week 2.

## 10. Vite Env Precedence (Operational)

For `vite` runtime resolution, effective precedence is:

1. `.env.local`
2. `.env.[mode].local`
3. `.env.[mode]`
4. `.env`

Operational rule for this project:
- Keep developer overrides in `.env.local` only.
- Keep shared non-secret defaults in `.env.development` / `.env.staging`.
- Keep `.env.example` synchronized with required key contract.

## 11. Runtime Validation Contract (`env.ts`)

`src/shared/config/env.ts` should:
- assert `VITE_API_BASE_URL` exists and parses as a valid URL;
- normalize trailing slash once;
- coerce `VITE_API_TIMEOUT_MS` to number with fallback `15000`;
- expose a typed readonly object consumed by `src/shared/api/client.ts`.

## 12. Cross-Origin and Local Dev Risk Note

Because frontend and API may run on different origins in local/dev, `VITE_API_BASE_URL` must point to an API origin that allows browser CORS from the frontend origin.

If CORS fails, do not workaround in UI code; fix backend CORS policy or local proxy configuration.

## 13. Env Consumption Guardrails

To prevent config sprawl in Week 1:

- `import.meta.env` access is allowed only in `src/shared/config/env.ts`.
- All other modules must consume the exported typed config object.
- Missing required env should throw a clear startup error in development.
- In production-like modes, missing required env should fail fast before first API call.

## 14. Local/Dev/Staging Runtime Matrix

| Runtime | Expected `VITE_APP_ENV` | Base URL source | Secret source |
|---|---|---|---|
| Local developer run | `local` | `.env.local` (or fallback `.env.example` values) | developer local file only |
| Shared development | `development` | `.env.development` | CI/secret store injection if needed |
| Staging | `staging` | `.env.staging` | staging secret manager / pipeline vars |

Operational note:
- Keep committed env files non-secret.
- If keys are required in dev/staging, inject through environment variables in CI/CD, not committed files.
