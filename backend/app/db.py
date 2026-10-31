# PLACEHOLDER - owner A replaces (tables, triggers per dialect, batch inserts)
"""Database engine and session from DATABASE_URL: SQLite locally, Postgres when deployed."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


engine = create_engine(settings.database_url, connect_args=_connect_args(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


IMMUTABLE_TABLES = ("alert", "case_event")


def init_db() -> None:
    from app import models  # noqa: F401  (registers the tables on Base)

    Base.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":  # Postgres parity is deferred until deployment
        return
    with engine.begin() as conn:
        for table in IMMUTABLE_TABLES:
            for action in ("UPDATE", "DELETE"):
                conn.execute(text(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
                    f"BEGIN SELECT RAISE(ABORT, '{table} rows are immutable'); END"
                ))


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
