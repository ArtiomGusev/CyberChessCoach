"""Storage-layer schema initialiser.

Pre-2026-05-09 this module owned a separate raw-sqlite3 database
(``data/seca.db``) for the ``games`` / ``moves`` / ``explanations`` /
``repertoire`` / ``bandit_weights`` tables, while the auth tables lived
in SQLAlchemy.  Production deployments using Postgres for auth ended up
with foreign-key violations on ``/game/start`` because the games table
sat in a different physical database from the players table.

Post-migration every table is modelled in SQLAlchemy
(``llm/seca/storage/models.py``) and lives in the SQLAlchemy database
selected by ``DATABASE_URL`` (Postgres in prod, SQLite in dev/tests).
``init_db`` is preserved as a thin wrapper around the canonical
``init_schema`` so existing call sites in ``server.py`` lifespan and a
handful of tests don't need to change names.

``DB_PATH`` and ``get_conn`` were the raw-sqlite3 entrypoints used by
``repo.py`` and a handful of tests; both are deprecated.  Tests should
swap the SQLAlchemy engine via the ``temp_db`` fixture instead of
poking ``DB_PATH``.  ``get_conn`` raises ``RuntimeError`` so any caller
that the migration missed fails loudly with a discoverable message.
"""

from __future__ import annotations

from pathlib import Path

# Kept as a module-level constant for backward compatibility with a
# small number of legacy callers (e.g. ``llm/seca/seca_doctor.py``)
# that read it as a default location for cleanup operations.  The path
# is no longer authoritative — the SQLAlchemy engine derived from
# ``DATABASE_URL`` is the source of truth.
DB_PATH = Path("data/seca.db")


def get_conn():  # pragma: no cover - deprecated, raises in CI
    """Removed: raw sqlite3 connections are no longer supported.

    Pre-migration this returned a ``sqlite3.Connection`` against
    ``DB_PATH``.  Post-migration ``games`` / ``moves`` /
    ``explanations`` / ``repertoire`` / ``bandit_weights`` live in the
    SQLAlchemy engine bound by ``llm/seca/auth/router.py:engine``;
    callers must use ``llm/seca/storage/repo.py`` helpers (or
    ``SessionLocal`` directly) instead.  Raising loud here surfaces any
    leftover caller during CI rather than silently routing to a stale
    SQLite file.
    """
    raise RuntimeError(
        "llm.seca.storage.db.get_conn() was removed in the SQLAlchemy "
        "migration. Use the helpers in llm.seca.storage.repo or open a "
        "SessionLocal() from llm.seca.auth.router instead."
    )


def init_db() -> None:
    """Initialise the storage schema.

    Delegates to ``llm.seca.auth.router.init_schema`` so all tables
    (auth, events, brain, analytics, storage) are created in one pass
    against the same SQLAlchemy engine — the failure mode that used to
    be possible (one DB has the players row, another DB has the games
    row, FK violation) can no longer occur.

    Idempotent: ``Base.metadata.create_all`` is a no-op when the tables
    already exist.  Safe to call from FastAPI lifespan, the test
    conftest fixture, or maintenance scripts.
    """
    # Late import to avoid a circular: auth.router imports storage.models,
    # storage.models imports auth.models for Base, and storage.repo
    # imports auth.router for SessionLocal.  Importing init_schema lazily
    # here keeps storage.db importable without forcing the full router
    # module to load.
    from llm.seca.auth.router import init_schema

    init_schema()
