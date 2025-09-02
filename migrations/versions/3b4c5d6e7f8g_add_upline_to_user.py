"""Add upline column to User model

Revision ID: 3b4c5d6e7f8g
Revises: f2a9b8c7d6f1
Create Date: 2025-09-02 10:15:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b4c5d6e7f8g'
down_revision = 'f2a9b8c7d6f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('upline', sa.String(length=512), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('upline')
