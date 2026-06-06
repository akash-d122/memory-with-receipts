"""Create operational memory tables

Revision ID: 001
Revises: None
Create Date: 2025-01-01 00:00:00.000000

Creates the foundational operational memory tables from Phase 0/1:
- sources, memories, evidence (core memory models)
- source_records, evidence_records, memory_records, provenance_links (operational models)
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Core memory models ---

    op.create_table(
        "sources",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("uri", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_metadata", sa.dialects.postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "memories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("normalized_subject", sa.String(255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "memory_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memories.id"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("extraction_method", sa.String(100), nullable=False),
        sa.Column("verification_status", sa.String(50), nullable=False),
    )

    # --- Operational models ---

    op.create_table(
        "source_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(80), nullable=False, index=True),
        sa.Column("source_identifier", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(40), nullable=False, index=True),
        sa.Column("environment", sa.String(80), nullable=False, index=True),
        sa.Column("service_name", sa.String(120), nullable=False, index=True),
        sa.Column("host_name", sa.String(120), nullable=True, index=True),
        sa.Column("raw_payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index(
        "ix_source_records_operational_lookup",
        "source_records",
        ["environment", "service_name", "host_name", "severity"],
    )

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_record_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_records.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("evidence_type", sa.String(80), nullable=False, index=True),
        sa.Column("evidence_key", sa.String(120), nullable=False, index=True),
        sa.Column("evidence_value", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "memory_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("memory_key", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(80), nullable=False, index=True),
        sa.Column("status", sa.String(40), nullable=False, index=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("freshness_score", sa.Float(), nullable=False),
        sa.Column("contradiction_flag", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )

    op.create_index(
        "ix_memory_records_type_status_recent",
        "memory_records",
        ["memory_type", "status", "last_seen_at"],
    )

    op.create_table(
        "provenance_links",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "memory_record_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memory_records.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_record_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_records.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "evidence_record_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_records.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("link_reason", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provenance_links")
    op.drop_table("memory_records")
    op.drop_table("evidence_records")
    op.drop_table("source_records")
    op.drop_table("evidence")
    op.drop_table("memories")
    op.drop_table("sources")
