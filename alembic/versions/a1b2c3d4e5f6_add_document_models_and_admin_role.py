"""add_document_models_and_admin_role

Revision ID: a1b2c3d4e5f6
Revises: 3ff48f925b87
Create Date: 2026-08-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3ff48f925b87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar is_admin a users
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False))
    
    # Crear tabla documents
    op.create_table(
        'documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('state', sa.String(50), nullable=False, index=True),
        sa.Column('municipality', sa.String(100), nullable=True, index=True),
        sa.Column('document_type', sa.String(50), server_default='general'),
        sa.Column('source', sa.String(50), server_default='admin'),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('index_path', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('version', sa.Integer(), server_default='1'),
        sa.Column('uploaded_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Crear tabla document_suggestions
    op.create_table(
        'document_suggestions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('state', sa.String(50), nullable=False),
        sa.Column('municipality', sa.String(100), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('document_suggestions')
    op.drop_table('documents')
    op.drop_column('users', 'is_admin')
