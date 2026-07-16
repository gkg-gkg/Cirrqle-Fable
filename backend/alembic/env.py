"""Alembic environment — wired to the app's own engine and models.

We deliberately reuse `app.db.engine` (which reads DATABASE_URL / falls back to
SQLite exactly like the running server) and `SQLModel.metadata` (populated by
importing app.models), so migrations always target the same database and schema
the app uses — no duplicated connection settings in alembic.ini.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

# Make the `app` package importable when alembic is run from the backend/ dir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()  # read backend/.env so DATABASE_URL is available, like main.py

from app.db import engine  # noqa: E402  (same engine the server uses)
import app.models  # noqa: E402,F401  (import registers every table on the metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# All SQLModel tables live on this shared metadata; used for autogenerate.
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (alembic upgrade --sql)."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the live database using the app's engine."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect column type changes, not just add/drop
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
