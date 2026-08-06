"""add pgvector extension and document_embeddings table

Revision ID: 003_add_pgvector
Revises: 002_add_reset_token
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import VECTOR

revision: str = "003_add_pgvector"
down_revision: Union[str, None] = "002_add_reset_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create document_embeddings table
    op.create_table(
        "document_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.execute("""
        CREATE INDEX idx_embedding_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (
            m = 16,
            ef_construction = 64
        )
        """)

    # Índice B-tree para búsquedas por documento
    op.create_index(
        "idx_embedding_document_id",
        "document_embeddings",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_table("document_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
