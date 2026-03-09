# ADR 0003: API Key Authentication for MVP

- Status: Accepted
- Date: 2026-03-08

## Context

MVP requires low-friction machine-to-machine auth for API-first integration. Full OIDC/SSO rollout is heavier and not required for initial pilots.

## Decision

Use tenant-scoped API keys:
- Sent via `X-API-Key` header.
- Stored hashed in DB (never plaintext).
- Support create/rotate/revoke lifecycle.
- Include key prefix for operator diagnostics.

## Consequences

Positive:
- Fast implementation and easy client integration.
- Works well for backend automation use cases.

Negative:
- No end-user identity granularity (deferred to v2).
- Key leak risk requires strong secret handling and rotation support.
