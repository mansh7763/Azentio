"""Database engine and session from DATABASE_URL: SQLite locally, Postgres when deployed."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def driver_url(url: str) -> str:
    """Hosted Postgres gives postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _connect_args(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


DATABASE_URL = driver_url(settings.database_url)
engine = create_engine(DATABASE_URL, connect_args=_connect_args(DATABASE_URL), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


IMMUTABLE_TABLES = ("alert", "case_event")


def init_db() -> None:
    from app import models  # noqa: F401  (registers the tables on Base)

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text(
                "CREATE OR REPLACE FUNCTION refuse_change() RETURNS trigger AS $$ BEGIN "
                "RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql"
            ))
        for table in IMMUTABLE_TABLES:
            for action in ("UPDATE", "DELETE"):
                name = f"{table}_no_{action.lower()}"
                if engine.dialect.name == "postgresql":
                    conn.execute(text(f"DROP TRIGGER IF EXISTS {name} ON {table}"))
                    conn.execute(text(f"CREATE TRIGGER {name} BEFORE {action} ON {table} "
                                      "FOR EACH ROW EXECUTE FUNCTION refuse_change()"))
                else:
                    conn.execute(text(f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} "
                                      f"BEGIN SELECT RAISE(ABORT, '{table} rows are immutable'); END"))


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
