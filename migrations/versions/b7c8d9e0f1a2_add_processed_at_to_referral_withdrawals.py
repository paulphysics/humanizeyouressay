"""Add processed_at column to referral_withdrawals

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2025-09-03 23:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    print("Adding processed_at column to referral_withdrawals...")
    # op.add_column('referral_withdrawals', sa.Column('processed_at', sa.DateTime(), nullable=True))
    print("Column processed_at added successfully.")


def downgrade():
    print("Dropping processed_at column from referral_withdrawals...")
    op.drop_column('referral_withdrawals', 'processed_at')
    print("Column processed_at dropped.")
