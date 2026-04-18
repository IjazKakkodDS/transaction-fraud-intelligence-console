"""
Alembic migration environment.

DATABASE_URL is read from the environment (or a .env file).
The table metadata is imported from src/db/postgres_logger so the
migration target always stays in sync with the application schema.
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------

# Load .env so DATABASE_URL is available when running alembic from the shell.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Copy .env.example to .env and set a Postgres connection string "
        "before running Alembic migrations."
    )

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------

config = context.config

# Inject DATABASE_URL at runtime — it is never written into alembic.ini.
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Target metadata
# Import from postgres_logger so Alembic autogenerate sees the live schema.
# ---------------------------------------------------------------------------

from src.db.postgres_logger import metadata as target_metadata  # noqa: E402

# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.

    Emits SQL to stdout. Useful for generating migration scripts to review
    before applying, or for environments where direct DB access is restricted.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Compare server defaults and column types for autogenerate accuracy.
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations with a live database connection.

    This is the standard path used by `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No connection pooling during migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
