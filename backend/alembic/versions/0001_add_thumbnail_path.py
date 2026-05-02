"""add thumbnail_path to videos

Revision ID: 0001
Revises:
Create Date: 2026-05-02

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('videos', sa.Column('thumbnail_path', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('videos', 'thumbnail_path')
