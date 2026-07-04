"""Database setup: a single SQLite file, accessed through SQLModel.

SQLite is a database that lives in one file on disk — no separate database
server to run. It is perfect for getting started; we can move to Postgres later
without changing any of the calling code, only this file.
"""
import os

from sqlmodel import SQLModel, Session, create_engine

DB_PATH = os.environ.get("CIRQLE_DB_PATH", "cirqle.db")

# check_same_thread=False lets FastAPI's worker threads share the connection.
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
