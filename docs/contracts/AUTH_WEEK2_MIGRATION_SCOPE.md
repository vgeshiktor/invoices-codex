# Week 2 Auth Migration Scope (BE-001)

Status: Draft frozen for Week 2 implementation start (Day 0, 2026-03-11).

## Goal

Add minimum schema needed for tenant user login, session refresh/logout, and `GET /v1/me`.

## Existing Baseline

- Existing multi-tenant core tables already use `saas_*` naming and `String(36)` UUID IDs.
- Tenant boundary source of truth exists in `saas_tenants`.
- Existing auth model is API-key based (`saas_api_keys`) and remains in use.

## Existing Table Changes

### `saas_tenants`

Add tenant slug support required by `POST /auth/login`.

Columns:

- `slug` `String(64)` not null

Constraints and indexes:

- `uq_saas_tenants_slug` unique (`slug`)

Notes:

- Backfill strategy for existing rows: one-time generated slug from name with collision-safe suffixing.
- Slug immutability in Week 2 (updates deferred).

## New Tables

### 1) `saas_users`

Purpose: tenant-user identity and credentials.

Columns:

- `id` `String(36)` PK
- `email` `String(320)` not null
- `email_normalized` `String(320)` not null
- `password_hash` `String(255)` not null
- `full_name` `String(255)` null
- `is_active` `Boolean` not null default `true`
- `last_login_at` `DateTime(timezone=True)` null
- `created_at` `DateTime(timezone=True)` not null
- `updated_at` `DateTime(timezone=True)` not null

Constraints and indexes:

- `uq_saas_users_email_normalized` unique (`email_normalized`)

### 2) `saas_tenant_memberships`

Purpose: map users to tenants and role context.

Columns:

- `id` `String(36)` PK
- `tenant_id` `String(36)` FK -> `saas_tenants.id` not null
- `user_id` `String(36)` FK -> `saas_users.id` not null
- `role` `String(32)` not null (Week 2 baseline: `owner|admin|member|viewer`)
- `status` `String(32)` not null default `active` (`active|disabled|invited`)
- `created_at` `DateTime(timezone=True)` not null
- `updated_at` `DateTime(timezone=True)` not null

Constraints and indexes:

- `uq_saas_tenant_memberships_tenant_user` unique (`tenant_id`, `user_id`)
- `ix_saas_tenant_memberships_tenant_id` on (`tenant_id`)
- `ix_saas_tenant_memberships_user_id` on (`user_id`)
- `ix_saas_tenant_memberships_tenant_role` on (`tenant_id`, `role`)

### 3) `saas_auth_sessions`

Purpose: persistent tenant-bound auth sessions with refresh-token lifecycle.

Columns:

- `id` `String(36)` PK
- `tenant_id` `String(36)` FK -> `saas_tenants.id` not null
- `user_id` `String(36)` FK -> `saas_users.id` not null
- `membership_id` `String(36)` FK -> `saas_tenant_memberships.id` not null
- `refresh_token_hash` `String(64)` not null (SHA-256 hex of opaque refresh token)
- `created_at` `DateTime(timezone=True)` not null
- `updated_at` `DateTime(timezone=True)` not null
- `last_seen_at` `DateTime(timezone=True)` null
- `access_expires_at` `DateTime(timezone=True)` not null
- `refresh_expires_at` `DateTime(timezone=True)` not null
- `revoked_at` `DateTime(timezone=True)` null
- `revoke_reason` `String(64)` null
- `created_ip` `String(64)` null
- `created_user_agent` `String(512)` null

Constraints and indexes:

- `uq_saas_auth_sessions_refresh_token_hash` unique (`refresh_token_hash`)
- `ix_saas_auth_sessions_tenant_user` on (`tenant_id`, `user_id`)
- `ix_saas_auth_sessions_membership_id` on (`membership_id`)
- `ix_saas_auth_sessions_refresh_expires_at` on (`refresh_expires_at`)
- `ix_saas_auth_sessions_revoked_at` on (`revoked_at`)

## Migration Notes

- No destructive changes to existing tables in Week 2.
- No backfill required for existing API-key tenants.
- Existing `saas_audit_events.actor` remains string-based in Week 2 (no schema change required).
- Keep all new IDs as `String(36)` UUID strings for consistency with current models/migrations.

## Week 2 Data/Behavioral Rules

- Passwords are never stored in plaintext; only `password_hash`.
- `email_normalized` is lowercased and trimmed before unique check.
- Session refresh rotates `refresh_token_hash` in-place for the session row.
- Logout sets `revoked_at` and optional `revoke_reason`.
- Tenant-safe lookups always include tenant binding from membership/session.

## Migration Deliverables (Day 1-2)

1. Alembic migration adding the three tables with indexes/constraints above.
2. SQLAlchemy model updates for the new entities.
3. Minimal seed fixture strategy for tests (one tenant, one active user membership).

## Open Decisions Blocking Migration Start

1. Password hash algorithm/cost parameters (`argon2id` vs `bcrypt`) and upgrade policy.
2. Refresh token lifecycle model (`single row rotate-in-place` vs `token family` child table).
3. Whether to add optional `saas_auth_sessions.parent_session_id` now for replay lineage.
4. Whether `saas_users.email_normalized` should be globally unique (current scope) or provider-scoped later.

## Explicitly Deferred

- Password reset tokens and invite flows.
- Global session management UI (logout all devices).
- MFA and external IdP federation.
- Postgres RLS policy migration for auth tables.
