"""Lichess ingestion adapter — outside the Mode-2 trust boundary.

This package imports user games + profile data from the public Lichess API
and lands them in the existing ``game_events`` table as a sibling source
to in-app gameplay (``source='lichess'`` vs ``source='app'``).

Trust-boundary note
-------------------
Lichess can return its own Stockfish evaluations when called with
``evals=true``.  These are explicitly NOT trusted by this codebase: per
``docs/ARCHITECTURE.md`` engine truth comes from the local engine pool
only.  The client therefore requests Lichess with ``evals=false`` and the
import path never copies any Lichess-derived eval into ``GameEvent``
fields that the ESV / coaching pipeline consumes.  ESV for imported games
is produced lazily by re-analysing the PGN with the local Stockfish pool
when (and only when) the user opens that game for review.

Per-player import-job mutex
---------------------------
``get_player_import_lock`` returns a process-wide ``threading.Lock``
keyed on ``player_id``.  It is held around the
``SELECT … FROM lichess_import_jobs WHERE player_id=? AND status IN
('queued','running')`` / ``INSERT`` critical section in
``start_import_job``: two concurrent ``POST /lichess/import`` calls
from the same player would otherwise both see "no active job" and both
``executor.submit`` a worker, doubling Lichess API cost and racing on
the per-game unique constraint.

The same property is additionally enforced on Postgres by a partial
unique index (created in ``init_schema``).  SQLite cannot express the
predicate portably, so dev relies on the lock alone.  The lock is also
the primary guard on Postgres — defense in depth, not redundancy.
"""

import threading

# Created lazily so the lock dict only grows by linked-player count
# rather than holding a slot for every registered user.  ``_locks_guard``
# protects the dict mutation itself; without it, two threads racing on
# ``get_player_import_lock("alice")`` could each create a fresh lock and
# proceed to step on each other in start_import_job.
_player_import_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def get_player_import_lock(player_id: str) -> threading.Lock:
    """Return (creating if needed) the per-player lock for import-job creation.

    Safe to call concurrently from any thread.  The returned lock must
    be acquired with ``with`` around the ``start_import_job`` SELECT +
    INSERT critical section; do NOT hold it across the long-running
    Lichess stream — that would serialise *all* imports for the same
    player even when the worker is happy to run.
    """
    with _locks_guard:
        lock = _player_import_locks.get(player_id)
        if lock is None:
            lock = threading.Lock()
            _player_import_locks[player_id] = lock
        return lock
