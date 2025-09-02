"""Add phone_number to User and create referral_withdrawals table

Revision ID: 5e6f7g8h9i0j
Revises: 4d5e6f7g8h9i
Create Date: 2025-09-02 15:30:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e6f7g8h9i0j'
down_revision = '4d5e6f7g8h9i'
branch_labels = None
depends_on = None


def upgrade():
    # --- Add phone_number column to User ---
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("phone_number", sa.String(length=20), nullable=False, server_default=""))
        batch_op.create_unique_constraint("uq_user_phone_number", ["phone_number"])

    # Remove server_default after backfilling existing users
    op.alter_column("user", "phone_number", server_default=None)

    # --- Create referral_withdrawals table ---
    op.create_table(
        "referral_withdrawals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(length=128), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime, nullable=True),
    )


def downgrade():
    # Drop referral_withdrawals table
    op.drop_table("referral_withdrawals")

    # Remove phone_number from User
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_constraint("uq_user_phone_number", type_="unique")
        batch_op.drop_column("phone_number")
