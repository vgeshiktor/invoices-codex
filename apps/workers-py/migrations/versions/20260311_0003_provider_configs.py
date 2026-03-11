"""Add provider configuration schema.

Revision ID: 20260311_0003
Revises: 20260311_0002
Create Date: 2026-03-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260311_0003"
down_revision: Union[str, None] = "20260311_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saas_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("connection_status", sa.String(length=32), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("oauth_access_token_enc", sa.Text(), nullable=True),
        sa.Column("oauth_refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_type",
            name="uq_saas_provider_configs_tenant_provider",
        ),
    )
    op.create_index(
        "ix_saas_provider_configs_tenant_id",
        "saas_provider_configs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_saas_provider_configs_connection_status",
        "saas_provider_configs",
        ["connection_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_saas_provider_configs_connection_status",
        table_name="saas_provider_configs",
    )
    op.drop_index("ix_saas_provider_configs_tenant_id", table_name="saas_provider_configs")
    op.drop_table("saas_provider_configs")
