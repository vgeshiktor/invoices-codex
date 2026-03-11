"""Add tenant user/session auth schema.

Revision ID: 20260311_0002
Revises: 20260308_0001
Create Date: 2026-03-11
"""

from __future__ import annotations

import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260311_0002"
down_revision: Union[str, None] = "20260308_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    if not value:
        return "tenant"
    return value[:64]


def upgrade() -> None:
    op.add_column("saas_tenants", sa.Column("slug", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    rows = list(bind.execute(sa.text("select id, name from saas_tenants")).mappings())
    used: set[str] = set()
    for row in rows:
        base = _slugify(str(row["name"] or ""))
        candidate = base
        suffix = 1
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used.add(candidate)
        bind.execute(
            sa.text("update saas_tenants set slug = :slug where id = :tenant_id"),
            {"slug": candidate, "tenant_id": row["id"]},
        )

    with op.batch_alter_table("saas_tenants") as batch_op:
        batch_op.alter_column("slug", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint("uq_saas_tenants_slug", ["slug"])

    op.create_table(
        "saas_users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized", name="uq_saas_users_email_normalized"),
    )

    op.create_table(
        "saas_tenant_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["saas_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_saas_tenant_memberships_tenant_user"),
    )
    op.create_index(
        "ix_saas_tenant_memberships_tenant_id",
        "saas_tenant_memberships",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_saas_tenant_memberships_user_id",
        "saas_tenant_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_saas_tenant_memberships_tenant_role",
        "saas_tenant_memberships",
        ["tenant_id", "role"],
        unique=False,
    )

    op.create_table(
        "saas_auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("membership_id", sa.String(length=36), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=64), nullable=True),
        sa.Column("created_ip", sa.String(length=64), nullable=True),
        sa.Column("created_user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["membership_id"], ["saas_tenant_memberships.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["saas_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_saas_auth_sessions_refresh_token_hash"),
    )
    op.create_index(
        "ix_saas_auth_sessions_tenant_user",
        "saas_auth_sessions",
        ["tenant_id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_saas_auth_sessions_membership_id",
        "saas_auth_sessions",
        ["membership_id"],
        unique=False,
    )
    op.create_index(
        "ix_saas_auth_sessions_refresh_expires_at",
        "saas_auth_sessions",
        ["refresh_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_saas_auth_sessions_revoked_at", "saas_auth_sessions", ["revoked_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_saas_auth_sessions_revoked_at", table_name="saas_auth_sessions")
    op.drop_index("ix_saas_auth_sessions_refresh_expires_at", table_name="saas_auth_sessions")
    op.drop_index("ix_saas_auth_sessions_membership_id", table_name="saas_auth_sessions")
    op.drop_index("ix_saas_auth_sessions_tenant_user", table_name="saas_auth_sessions")
    op.drop_table("saas_auth_sessions")

    op.drop_index("ix_saas_tenant_memberships_tenant_role", table_name="saas_tenant_memberships")
    op.drop_index("ix_saas_tenant_memberships_user_id", table_name="saas_tenant_memberships")
    op.drop_index("ix_saas_tenant_memberships_tenant_id", table_name="saas_tenant_memberships")
    op.drop_table("saas_tenant_memberships")

    op.drop_table("saas_users")

    with op.batch_alter_table("saas_tenants") as batch_op:
        batch_op.drop_constraint("uq_saas_tenants_slug", type_="unique")
        batch_op.drop_column("slug")
