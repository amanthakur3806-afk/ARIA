"""Database engine, session factory and the get_db() dependency."""
import os
from collections.abc import Iterator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def _database_url() -> str | None:
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    # Accept a plain postgresql:// URL and use the psycopg (v3) driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


_db_url = _database_url()
if _db_url:
    try:
        engine = create_engine(_db_url, pool_pre_ping=True)
        SessionLocal = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
    except Exception:
        engine = None
        SessionLocal = None
else:
    engine = None
    SessionLocal = None


def get_db() -> Iterator[Session]:
    """FastAPI-style dependency: one session per request, always closed.

        @router.get("/x")
        def route(db: Session = Depends(get_db)): ...
    """
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set for relational session.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """For scripts and background jobs: commits on success, rolls back on error."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set for relational session.")
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
