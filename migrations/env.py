# migrations/env.py
import os
from logging.config import fileConfig

from flask import current_app
from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# --- KEY CHANGE: Comment out this line to prevent FileNotFoundError ---
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)
# --- END OF KEY CHANGE ---


# --- This is the key change ---
# Import your app's models here so Alembic can see them.
# The 'run.py' or 'FLASK_APP' environment variable should point to your app factory.
from humanizer_app.models import db
target_metadata = db.metadata
# --- End of key change ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_flask_app():
    """
    Dynamically loads the Flask app.
    This is necessary for Alembic to work with the app context.
    """
    from humanizer_app import create_app
    return create_app()

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    app = get_flask_app()
    url = app.config.get('SQLALCHEMY_DATABASE_URI')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    app = get_flask_app()
    with app.app_context():
        # Connect to the database using the app's configuration
        connectable = db.get_engine()

        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
