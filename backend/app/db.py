"""Database setup, accessed through SQLModel.

Two modes, chosen by whether DATABASE_URL is set:
  • DATABASE_URL set  -> production: Amazon RDS PostgreSQL (a managed database
    server AWS runs for us — automatic backups, survives instance changes).
  • DATABASE_URL unset -> local dev: a single SQLite file on disk (no server).

All the calling code is identical either way — only the engine below differs.
"""
import os

from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Postgres (RDS). pool_pre_ping quietly drops dead connections so a
    # long-idle server doesn't error on its next query.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # SQLite. check_same_thread=False lets FastAPI's worker threads share it.
    DB_PATH = os.environ.get("CIRQLE_DB_PATH", "cirqle.db")
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )


def init_db() -> None:
    """Create any tables that don't exist yet (based on the SQLModel models)."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Yield a database session for one request, then close it (FastAPI dependency)."""
    with Session(engine) as session:
        yield session
