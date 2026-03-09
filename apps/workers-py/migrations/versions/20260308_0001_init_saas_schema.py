"""Initial SaaS schema.

Revision ID: 20260308_0001
Revises:
Create Date: 2026-03-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260308_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saas_tenants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "saas_api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_saas_api_keys_tenant_id", "saas_api_keys", ["tenant_id"], unique=False)

    op.create_table(
        "saas_invoice_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_saas_invoice_files_tenant_id", "saas_invoice_files", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_saas_invoice_files_content_sha256",
        "saas_invoice_files",
        ["content_sha256"],
        unique=False,
    )

    op.create_table(
        "saas_parse_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("queue_job_id", sa.String(length=64), nullable=True),
        sa.Column("debug", sa.Boolean(), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_saas_parse_jobs_idempotency"),
    )
    op.create_index("ix_saas_parse_jobs_tenant_id", "saas_parse_jobs", ["tenant_id"], unique=False)
    op.create_index("ix_saas_parse_jobs_status", "saas_parse_jobs", ["status"], unique=False)

    op.create_table(
        "saas_parse_job_files",
        sa.Column("parse_job_id", sa.String(length=36), nullable=False),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["saas_invoice_files.id"]),
        sa.ForeignKeyConstraint(["parse_job_id"], ["saas_parse_jobs.id"]),
        sa.PrimaryKeyConstraint("parse_job_id", "file_id"),
    )

    op.create_table(
        "saas_invoice_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("parse_job_id", sa.String(length=36), nullable=False),
        sa.Column("vendor", sa.String(length=255), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("invoice_number", sa.String(length=128), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("invoice_total", sa.Float(), nullable=True),
        sa.Column("invoice_vat", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parse_job_id"], ["saas_parse_jobs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_saas_invoice_records_parse_job_id",
        "saas_invoice_records",
        ["parse_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_saas_invoice_records_tenant_id", "saas_invoice_records", ["tenant_id"], unique=False
    )

    op.create_table(
        "saas_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("queue_job_id", sa.String(length=64), nullable=True),
        sa.Column("requested_formats_json", sa.Text(), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_saas_reports_idempotency"),
    )
    op.create_index("ix_saas_reports_status", "saas_reports", ["status"], unique=False)
    op.create_index("ix_saas_reports_tenant_id", "saas_reports", ["tenant_id"], unique=False)

    op.create_table(
        "saas_report_parse_jobs",
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("parse_job_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parse_job_id"], ["saas_parse_jobs.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["saas_reports.id"]),
        sa.PrimaryKeyConstraint("report_id", "parse_job_id"),
    )

    op.create_table(
        "saas_report_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["saas_reports.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_saas_report_artifacts_report_id", "saas_report_artifacts", ["report_id"], unique=False
    )
    op.create_index(
        "ix_saas_report_artifacts_tenant_id", "saas_report_artifacts", ["tenant_id"], unique=False
    )

    op.create_table(
        "saas_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_saas_audit_events_tenant_id", "saas_audit_events", ["tenant_id"], unique=False
    )

    op.create_table(
        "saas_idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["saas_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "scope", "idempotency_key", name="uq_saas_idempotency_scope_key"
        ),
    )
    op.create_index(
        "ix_saas_idempotency_records_tenant_id",
        "saas_idempotency_records",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_saas_idempotency_records_tenant_id", table_name="saas_idempotency_records")
    op.drop_table("saas_idempotency_records")

    op.drop_index("ix_saas_audit_events_tenant_id", table_name="saas_audit_events")
    op.drop_table("saas_audit_events")

    op.drop_table("saas_report_parse_jobs")

    op.drop_index("ix_saas_report_artifacts_tenant_id", table_name="saas_report_artifacts")
    op.drop_index("ix_saas_report_artifacts_report_id", table_name="saas_report_artifacts")
    op.drop_table("saas_report_artifacts")

    op.drop_index("ix_saas_reports_tenant_id", table_name="saas_reports")
    op.drop_index("ix_saas_reports_status", table_name="saas_reports")
    op.drop_table("saas_reports")

    op.drop_index("ix_saas_invoice_records_tenant_id", table_name="saas_invoice_records")
    op.drop_index("ix_saas_invoice_records_parse_job_id", table_name="saas_invoice_records")
    op.drop_table("saas_invoice_records")

    op.drop_table("saas_parse_job_files")

    op.drop_index("ix_saas_parse_jobs_status", table_name="saas_parse_jobs")
    op.drop_index("ix_saas_parse_jobs_tenant_id", table_name="saas_parse_jobs")
    op.drop_table("saas_parse_jobs")

    op.drop_index("ix_saas_invoice_files_content_sha256", table_name="saas_invoice_files")
    op.drop_index("ix_saas_invoice_files_tenant_id", table_name="saas_invoice_files")
    op.drop_table("saas_invoice_files")

    op.drop_index("ix_saas_api_keys_tenant_id", table_name="saas_api_keys")
    op.drop_table("saas_api_keys")

    op.drop_table("saas_tenants")
