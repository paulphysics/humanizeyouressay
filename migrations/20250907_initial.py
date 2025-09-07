"""Initial migration

Revision ID: 20250907_initial
Revises: 
Create Date: 2025-09-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers, used by Alembic.
revision = '20250907_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### Create tables ###
    op.create_table(
        'user',
        sa.Column('id', sa.String(length=128), primary_key=True),
        sa.Column('email', sa.String(length=120), nullable=False, unique=True),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('phone_number', sa.String(length=20), unique=True, nullable=True),
        sa.Column('referral_code', sa.String(length=20), unique=True, nullable=True),
        sa.Column('referred_by', sa.String(length=128), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('upline', sa.String(), nullable=True),
    )

    op.create_table(
        'wallet',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('balance', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('user_id', sa.String(length=128), sa.ForeignKey('user.id'), nullable=False, unique=True),
    )

    op.create_table(
        'task',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('external_reference', sa.String(length=120), nullable=False, unique=True, index=True),
        sa.Column('input_text', sa.Text, nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('amount_charged', sa.Float, nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default="'payment_initiated'"),
        sa.Column('humanized_output', sa.Text, nullable=True),
        sa.Column('output_word_count', sa.Integer, nullable=True),
        sa.Column('diff_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('user_id', sa.String(length=128), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('output_format', sa.String(length=50), nullable=True),
    )

    op.create_table(
        'transaction',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('wallet_id', sa.Integer, sa.ForeignKey('wallet.id'), nullable=False),
        sa.Column('is_reversed', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    )

    op.create_table(
        'conversation',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(length=128), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False, server_default="'New Conversation'"),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('model_key', sa.String(length=50), nullable=False),
    )

    op.create_table(
        'chat_message',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('conversation_id', sa.Integer, sa.ForeignKey('conversation.id'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'expense',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('expense_date', sa.Date, server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'referral_ledger',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(length=128), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('transaction_id', sa.Integer, sa.ForeignKey('transaction.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    op.create_table(
        'referral_withdrawals',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.String(length=128), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('status', sa.String(length=20), server_default="'pending'"),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('processed_at', sa.DateTime, nullable=True),
    )
    # ### End of tables ###


def downgrade():
    op.drop_table('referral_withdrawals')
    op.drop_table('referral_ledger')
    op.drop_table('expense')
    op.drop_table('chat_message')
    op.drop_table('conversation')
    op.drop_table('transaction')
    op.drop_table('task')
    op.drop_table('wallet')
    op.drop_table('user')
