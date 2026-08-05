"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("credits", sa.Integer(), server_default="5"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_verified", sa.Boolean(), server_default="false"),
        sa.Column("is_admin", sa.Boolean(), server_default="false"),
        sa.Column("verification_token", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # credit_transactions
    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # payments
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mp_payment_id", sa.String(255), unique=True),
        sa.Column("mp_preference_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="MXN"),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("extra_data", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # credit_packages
    op.create_table(
        "credit_packages",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_per_credit", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    credit_packages = sa.table(
        "credit_packages",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("credits", sa.Integer),
        sa.column("price", sa.Numeric),
        sa.column("price_per_credit", sa.Numeric),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        credit_packages,
        [
            {"id": "basico", "name": "Básico", "credits": 10, "price": 49.00, "price_per_credit": 4.90, "is_active": True},
            {"id": "estandar", "name": "Estándar", "credits": 30, "price": 99.00, "price_per_credit": 3.30, "is_active": True},
            {"id": "pro", "name": "Pro", "credits": 100, "price": 249.00, "price_per_credit": 2.49, "is_active": True},
        ],
    )

    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("document_type", sa.String(50), server_default="general"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), server_default="admin"),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("index_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_state", "documents", ["state"])

    # document_suggestions
    op.create_table(
        "document_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # document_types
    op.create_table(
        "document_types",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="5"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_document_types_state", "document_types", ["state"])

    # document_municipalities
    op.create_table(
        "document_municipalities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("municipality", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_document_municipalities_document_id",
        "document_municipalities",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_table("document_municipalities")
    op.drop_table("document_types")
    op.drop_table("document_suggestions")
    op.drop_table("documents")
    op.drop_table("credit_packages")
    op.drop_table("payments")
    op.drop_table("credit_transactions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
