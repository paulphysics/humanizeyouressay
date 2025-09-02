"""Add referral ledger table

Revision ID: 4d5e6f7g8h9i
Revises: 3b4c5d6e7f8g
Create Date: 2025-09-02 14:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d5e6f7g8h9i'
down_revision = '3b4c5d6e7f8g'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'referral_ledger',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(length=128), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('transaction_id', sa.Integer, sa.ForeignKey('transaction.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('referral_ledger')
