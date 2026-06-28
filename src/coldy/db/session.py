"""Engine + session management.

Synchronous SQLAlchemy is used deliberately: call volume (hundreds/day) is low
for a database, and sync sessions keep the dialer worker and in-call tool
handlers simple. Swap to async engines if you scale to high throughput.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db() -> None:
    """Create tables. For production, prefer Alembic migrations."""
    from . import models  # noqa: F401  (register mappers)
    from .base import Base

    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
