"""update vector dims to 768 for jina clip

Revision ID: 1a2b3c4d5e6f
Revises: efb17bbdead1
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, None] = 'efb17bbdead1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Drop the existing HNSW index (PostgreSQL prevents altering indexed vector columns)
    op.drop_index('content_embedding_idx', table_name='file_content', postgresql_using='hnsw')
    
    # 2. Alter the column type to 768 dimensions
    op.alter_column(
        'file_content', 'embedding',
        existing_type=Vector(384),
        type_=Vector(768),
        existing_nullable=False
    )

    # 3. Recreate the index for the new 768-dimensional space
    op.create_index(
        'content_embedding_idx',
        'file_content',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )


def downgrade() -> None:
    # 1. Drop the 768-dim index
    op.drop_index('content_embedding_idx', table_name='file_content', postgresql_using='hnsw')
    
    # 2. Revert the column type back to 384 dimensions
    op.alter_column(
        'file_content', 'embedding',
        existing_type=Vector(768),
        type_=Vector(384),
        existing_nullable=False
    )

    # 3. Recreate the original index
    op.create_index(
        'content_embedding_idx',
        'file_content',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )