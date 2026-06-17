"""Add chunk_embeddings table with pgvector

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:00.000000

Enables the pgvector extension, creates the chunk_embeddings table with a
vector column for storing embeddings, and adds an HNSW index for fast
cosine-similarity search.
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from memory_with_receipts.core.config import Settings

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    dim = Settings().embedding_dimension

    # Create chunk_embeddings table
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(dim), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("embedding_provider", sa.String(100), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=False),
    )

    # HNSW index for fast cosine-similarity search
    op.execute(
        "CREATE INDEX ix_chunk_embeddings_embedding_hnsw "
        "ON chunk_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunk_embeddings_embedding_hnsw")
    op.drop_table("chunk_embeddings")
    # Note: we do NOT drop the vector extension on downgrade because
    # other tables/migrations may depend on it.
