"""Add upline column to User model

Revision ID: 3b4c5d6e7f8g
Revises: 2a1b3c4d5e6f
Create Date: 2025-09-02 10:15:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b4c5d6e7f8g'
down_revision = '2a1b3c4d5e6f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('upline', sa.String(length=512), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('upline')
