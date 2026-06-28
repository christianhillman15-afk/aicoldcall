"""Shared fixtures: an isolated database for tests.

Unit tests use the per-test in-memory `session` fixture. Integration tests that
exercise the FastAPI app (which uses the global engine) get an isolated temp
DB — set here BEFORE any coldy module imports so settings pick it up.
"""

from __future__ import annotations

import os
import pathlib
import tempfile

_TESTDB = pathlib.Path(tempfile.gettempdir()) / "coldy_pytest.db"
os.environ["COLDY_DATABASE_URL"] = f"sqlite:///{_TESTDB}"
try:
    _TESTDB.unlink()
except FileNotFoundError:
    pass

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from coldy.db.base import Base  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()
