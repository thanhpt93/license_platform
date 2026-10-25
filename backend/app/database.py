from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import BACKEND_DIR, settings


def _resolve_database_url(raw_url: str) -> str:
    if raw_url == "sqlite:///./nova_license.db":
        return f"sqlite:///{(BACKEND_DIR / 'nova_license.db').as_posix()}"
    return raw_url


resolved_db_url = _resolve_database_url(settings.NOVA_DATABASE_URL)

connect_args = {}
if resolved_db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    resolved_db_url,
    connect_args=connect_args,
    future=True,
)

if resolved_db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
