#!/bin/sh
set -eu

stamp_legacy_sqlite_schema_if_needed() {
  python - <<'PY'
import os
import re
import sqlite3
from pathlib import Path


def sqlite_path_from_url(url: str) -> str | None:
    # Supports sqlite:///relative.db and sqlite:////absolute/path.db
    m = re.match(r"^sqlite:(/{3,})(.+)$", url)
    if not m:
        return None
    slashes, raw_path = m.groups()
    if len(slashes) >= 4:
        return "/" + raw_path.lstrip("/")
    return raw_path


db_url = os.environ.get("SAAS_DATABASE_URL", "")
db_path = sqlite_path_from_url(db_url)
if not db_path:
    raise SystemExit(0)

path = Path(db_path)
if not path.exists():
    raise SystemExit(0)

conn = sqlite3.connect(str(path))
try:
    cursor = conn.cursor()
    tables = {
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    def slugify(value: str) -> str:
        text = value.strip().lower()
        text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        return text or "tenant"

    # Fresh DB with no SaaS tables: no stamping needed.
    if "saas_tenants" not in tables:
        raise SystemExit(0)

    tenant_cols = {row[1] for row in cursor.execute("PRAGMA table_info('saas_tenants')").fetchall()}
    has_users = "saas_users" in tables
    has_provider_configs = "saas_provider_configs" in tables
    has_alembic_version_table = "alembic_version" in tables
    alembic_versions = []
    if has_alembic_version_table:
        alembic_versions = [
            row[0]
            for row in cursor.execute("SELECT version_num FROM alembic_version").fetchall()
            if row and row[0]
        ]

    # If alembic_version has a real revision already, nothing to patch/stamp.
    if alembic_versions:
        raise SystemExit(0)

    # Legacy inconsistent schema: auth/provider tables present but tenant slug is missing.
    if "slug" not in tenant_cols and (has_users or has_provider_configs):
        cursor.execute("ALTER TABLE saas_tenants ADD COLUMN slug VARCHAR(64)")
        rows = list(cursor.execute("SELECT id, name FROM saas_tenants").fetchall())
        used = set()
        for tenant_id, tenant_name in rows:
            base = slugify(str(tenant_name or "tenant"))
            candidate = base
            suffix = 2
            while candidate in used:
                suffix_text = f"-{suffix}"
                candidate = f"{base[: max(1, 64 - len(suffix_text))]}{suffix_text}"
                suffix += 1
            used.add(candidate)
            cursor.execute(
                "UPDATE saas_tenants SET slug = ? WHERE id = ?",
                (candidate, tenant_id),
            )
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_saas_tenants_slug ON saas_tenants(slug)")
        conn.commit()
        Path("/tmp/legacy_schema_repaired").write_text("slug", encoding="utf-8")

    if has_provider_configs:
        revision = "20260311_0003"
    elif has_users or "slug" in tenant_cols:
        revision = "20260311_0002"
    else:
        revision = "20260308_0001"

    Path("/tmp/legacy_alembic_stamp_rev").write_text(revision, encoding="utf-8")
except SystemExit:
    raise
finally:
    conn.close()
PY

  if [ -f /tmp/legacy_alembic_stamp_rev ]; then
    REVISION="$(cat /tmp/legacy_alembic_stamp_rev)"
    if [ -f /tmp/legacy_schema_repaired ]; then
      echo "Repaired legacy SQLite schema (tenant slug backfill)."
      rm -f /tmp/legacy_schema_repaired
    fi
    echo "Detected legacy SQLite schema without alembic_version; stamping revision ${REVISION}"
    alembic -c /app/alembic.ini stamp "${REVISION}"
    rm -f /tmp/legacy_alembic_stamp_rev
  fi
}

stamp_legacy_sqlite_schema_if_needed
alembic -c /app/alembic.ini upgrade head

exec python -m invplatform.cli.saas_api \
  --host 0.0.0.0 \
  --port 8081 \
  --database-url "${SAAS_DATABASE_URL:-sqlite:////data/files/invoices_saas.db}" \
  --storage-url "${SAAS_STORAGE_URL:-local:///data/files/saas_storage}" \
  --redis-url "${SAAS_REDIS_URL:-redis://redis:6379/0}" \
  --control-plane-api-key "${SAAS_CONTROL_PLANE_API_KEY:-dev-control-plane-key}" \
  --allow-insecure-auth-cookie
