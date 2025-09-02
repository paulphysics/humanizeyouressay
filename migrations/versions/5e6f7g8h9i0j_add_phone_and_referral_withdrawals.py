from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5e6f7g8h9i0j'
down_revision = '4d5e6f7g8h9i'
branch_labels = None
depends_on = None

def upgrade():
    # Add the column if it doesn't exist
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("phone_number", sa.String(length=20), nullable=True))

    # Convert empty strings to NULL
    op.execute("""
        UPDATE "user"
        SET phone_number = NULL
        WHERE phone_number = '';
    """)

    # Remove duplicate phone numbers, keep the lowest ID
    op.execute("""
        DELETE FROM "user" a
        USING "user" b
        WHERE a.id > b.id
        AND a.phone_number = b.phone_number
        AND a.phone_number IS NOT NULL;
    """)

    # Create a partial unique index for non-null phone numbers
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_phone_number
        ON "user"(phone_number)
        WHERE phone_number IS NOT NULL;
    """)


def downgrade():
    # Drop the unique index
    op.execute("DROP INDEX IF EXISTS uq_user_phone_number;")

    # Drop the phone_number column
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("phone_number")
