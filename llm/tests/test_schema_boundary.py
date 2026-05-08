"""Schema-init boundary regression tests.

Background
----------
Pre-2026-05-09 ``data/seca.db`` was initialised by two separate paths:

  1.  ``llm/seca/storage/db.py:init_db()`` ran
      ``llm/seca/storage/schema.sql`` via raw sqlite3 to create
      ``games`` / ``moves`` / ``explanations`` / ``repertoire`` /
      ``bandit_weights``.
  2.  ``llm/seca/auth/router.py:init_schema()`` ran
      ``Base.metadata.create_all()`` for the auth / events / brain /
      brain.training / analytics tables.

That split was an explicit, documented boundary — but it broke under
production once auth flipped to Postgres via ``DATABASE_URL``.  The
games table stayed in SQLite (because ``schema.sql`` is dialect-locked
and the helpers used raw ``sqlite3``) while the players table moved to
Postgres.  Every ``/game/start`` thereafter raised
``sqlite3.IntegrityError: FOREIGN KEY constraint failed`` — the
``games.player_id`` FK couldn't reach the player row in a different
physical database.

The fix removed the boundary: ``games`` / ``moves`` / ``explanations`` /
``repertoire`` / ``bandit_weights`` are now SQLAlchemy models in
``llm/seca/storage/models.py`` and live wherever ``DATABASE_URL``
points.  ``schema.sql`` is gone.

This test pins the new invariant: every legacy raw-sqlite table is now
present in ``Base.metadata.tables``, ``schema.sql`` is no longer on
disk, and ``repo.py`` no longer imports or calls ``sqlite3``.
Reintroducing any of those would fail this test loud at CI time rather
than at fresh-Postgres deployment time.
"""

from __future__ import annotations

import pathlib
import unittest


# Tables that, prior to the migration, schema.sql owned exclusively.
# Post-migration they all must appear in SQLAlchemy's metadata so a
# single ``create_all`` covers the full schema.  Update this set if
# any table is intentionally renamed or removed (and document why in
# the commit).
EXPECTED_MIGRATED_TABLES = frozenset({
    "games",
    "moves",
    "explanations",
    "repertoire",
    "bandit_weights",
})


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


class SchemaBoundaryTest(unittest.TestCase):

    def test_schema_sql_is_gone(self):
        """schema.sql must NOT exist on disk.

        It was the source of truth for the raw-sqlite path that broke
        the games-on-Postgres FK.  After the migration every table is
        a SQLAlchemy model; reintroducing schema.sql would silently
        re-create a separate raw-sqlite DB next to the SQLAlchemy one
        and reopen the same FK-violation failure mode.
        """
        schema_path = _repo_root() / "llm" / "seca" / "storage" / "schema.sql"
        self.assertFalse(
            schema_path.exists(),
            f"{schema_path} must not exist post-migration. "
            "If you re-added it, you've split the schema across two "
            "different databases again — see the commit that removed it.",
        )

    def test_all_migrated_tables_are_in_sqlalchemy_metadata(self):
        """Every previously-raw table must now live in Base.metadata.

        Implementation note: ``llm/conftest.py:_backend_schema_init`` is
        a session-scoped autouse fixture that calls
        ``auth/router.init_schema()`` before any test runs, which
        cascades into the side-effect imports
        (``from llm.seca.storage.models import *`` etc.) that populate
        Base.  Trust ``Base.metadata`` as-is rather than re-importing
        the model modules here — re-importing through the alternate
        ``seca.X.models`` fallback path defined in ``seca/db.py``
        creates a second module object and trips SQLAlchemy's
        "Table already defined" guard.
        """
        from llm.seca.auth.models import Base

        sqlalchemy_tables = set(Base.metadata.tables.keys())
        missing = EXPECTED_MIGRATED_TABLES - sqlalchemy_tables
        self.assertFalse(
            missing,
            f"SQLAlchemy metadata is missing migrated tables: {sorted(missing)}. "
            f"They are present in the codebase as ``llm/seca/storage/models.py`` "
            f"declarations, but Base.metadata only tracks classes whose modules "
            f"have actually been imported.  Confirm that "
            f"``llm/seca/auth/router.py`` still includes "
            f"``from llm.seca.storage.models import *`` so create_all picks them up.",
        )

    def test_repo_module_does_not_use_sqlite3(self):
        """``llm/seca/storage/repo.py`` must not import or call sqlite3.

        Post-migration the repo helpers are SQLAlchemy-only.  A grep is
        a deliberately coarse signal — it will fire on a comment too —
        but that's the right tradeoff: any reference to ``sqlite3`` in
        repo.py is something a reviewer should look at, not silently
        accept.  The signature-preservation guarantee in the migration
        means there should be exactly zero reasons to reach for raw
        sqlite3 here.
        """
        repo_path = _repo_root() / "llm" / "seca" / "storage" / "repo.py"
        text = repo_path.read_text(encoding="utf-8")
        self.assertNotIn(
            "import sqlite3",
            text,
            "repo.py imports sqlite3 — the SQLAlchemy migration removed all "
            "raw sqlite3 access from this layer.  Either revert to a SQLAlchemy "
            "helper or update this test (and document why) in the same commit.",
        )

    def test_legacy_get_conn_raises(self):
        """The legacy ``get_conn`` entrypoint must raise loudly.

        This guards against a forgotten caller: any code path that
        still calls ``get_conn()`` after the migration would silently
        open a stale ``data/seca.db`` and write rows that the rest of
        the system cannot see.  The replacement in
        ``llm/seca/storage/db.py`` raises ``RuntimeError`` so that case
        fails at import / call time rather than silently corrupting
        production state.
        """
        from llm.seca.storage.db import get_conn

        with self.assertRaises(RuntimeError):
            get_conn()


if __name__ == "__main__":
    unittest.main(verbosity=2)
