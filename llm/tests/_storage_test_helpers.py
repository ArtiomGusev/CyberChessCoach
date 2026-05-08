"""Shared helpers for tests that need a fresh per-test SQLAlchemy DB.

Background
----------
Pre-2026-05-09 each storage-touching test fixture monkey-patched
``llm.seca.storage.db.DB_PATH`` to a temp SQLite file and called
``init_db()`` to create the raw-sqlite schema.  After the
games/moves/explanations/repertoire/bandit_weights migration to
SQLAlchemy, ``DB_PATH`` no longer drives where rows go — the
``llm.seca.auth.router.engine`` does.  This helper centralises the
"point everything at a fresh SQLite file" dance so individual test
fixtures stay short.

Usage
-----
    @pytest.fixture()
    def temp_db(tmp_path, monkeypatch):
        from llm.tests._storage_test_helpers import bind_temp_database
        return bind_temp_database(tmp_path, monkeypatch)

The fixture returns the temp DB ``Path`` so callers that want to peek
directly at the file (e.g. raw sqlite3 inspection in legacy assertions)
still can.  The auto-cleanup is provided by the ``monkeypatch``
fixture: at test teardown the engine / SessionLocal references are
restored to the module-level values pointed at ``data/seca.db``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def bind_temp_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fresh SQLite file, bind the project engine to it, and
    create_all(Base.metadata) so tests can exercise the storage helpers
    without polluting the dev DB.

    Returns the temp DB path so a test can do its own raw inspection
    (rare — most tests just use the repo helpers).
    """
    from llm.seca.auth.models import Base
    from llm.seca.auth import router as auth_router

    db_file = tmp_path / "seca-test.db"
    url = f"sqlite:///{db_file.as_posix()}"
    test_engine = create_engine(url, connect_args={"check_same_thread": False})
    test_session = sessionmaker(bind=test_engine)

    # Point the project-wide engine + SessionLocal at the temp DB for
    # the duration of the test.  ``llm.seca.storage.repo`` re-resolves
    # ``SessionLocal`` on every call (via its ``_session()`` helper) so
    # this swap takes effect immediately.
    monkeypatch.setattr(auth_router, "engine", test_engine)
    monkeypatch.setattr(auth_router, "SessionLocal", test_session)

    Base.metadata.create_all(bind=test_engine)
    return db_file
