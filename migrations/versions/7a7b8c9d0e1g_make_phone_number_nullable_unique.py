"""Make phone_number nullable but unique when not null

Revision ID: 7a7b8c9d0e1g
Revises: 5e6f7g8h9i0j
Create Date: 2025-09-07 13:50:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6a7b8c9d0e1f'
down_revision = '5e6f7g8h9i0j'
branch_labels = None
depends_on = None


def upgrade():
    # Make phone_number nullable
    op.alter_column('user', 'phone_number',
                    existing_type=sa.String(length=20),
                    nullable=True)

    # Drop the old unique constraint
    op.drop_constraint('uq_user_phone_number', 'user', type_='unique')

    # Create a partial unique index (Postgres only)
    op.create_index('ix_user_phone_number_unique',
                    'user',
                    ['phone_number'],
                    unique=True,
                    postgresql_where=sa.text('phone_number IS NOT NULL'))


def downgrade():
    # Drop partial index
    op.drop_index('ix_user_phone_number_unique', table_name='user')

    # Recreate unique constraint
    op.create_unique_constraint('uq_user_phone_number', 'user', ['phone_number'])

    # Make phone_number NOT NULL again
    op.alter_column('user', 'phone_number',
                    existing_type=sa.String(length=20),
                    nullable=False)
