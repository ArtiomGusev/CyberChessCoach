-- Raw-sqlite schema for the storage tables that are NOT modelled by
-- SQLAlchemy.  Authoritative ownership map:
--
--   SQLAlchemy (Base.metadata.create_all in init_auth_schema)
--   ----------------------------------------------------------
--     players                       — auth/models.py:Player
--     sessions                      — auth/models.py:Session
--     game_events                   — events/models.py:GameEvent
--     analytics_events              — analytics/models.py:AnalyticsEvent
--     rating_updates                — brain/models.py:RatingUpdate
--     confidence_updates            — brain/models.py:ConfidenceUpdate
--     bandit_experiences            — brain/models.py:BanditExperience
--     training_decisions            — brain/training/models.py:TrainingDecision
--     training_outcomes             — brain/training/models.py:TrainingOutcome
--
--   This file (executed by storage/db.py:init_db)
--   ---------------------------------------------
--     games                         — repo.py game-lifecycle rows
--     moves                         — repo.py per-ply move log
--     explanations                  — repo.py /explanation_outcome learning score
--
-- Why split?  ``games``, ``moves``, ``explanations`` are written exclusively
-- by repo.py via raw sqlite3 (no ORM session) for the /move and
-- /explanation_outcome request paths.  Modelling them in SQLAlchemy would
-- gain nothing without porting repo.py too.  Leaving them here is the
-- minimal-change boundary; the duplicate ``players`` /
-- ``training_decisions`` / ``training_outcomes`` definitions that used to
-- live here were removed because they conflicted with the SQLAlchemy
-- models — schema.sql ran first under FastAPI lifespan, creating only
-- partial tables, then ``Base.metadata.create_all`` saw the tables
-- already present and skipped the missing columns.

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    player_id TEXT,
    result TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    -- In-progress checkpoint state for cross-device resume.  Populated
    -- by repo.checkpoint_game() during play; nulled out (or just left
    -- alongside finished_at) when the game completes.  The client
    -- pulls these via GET /game/active at cold-start when no local
    -- snapshot exists, e.g. after a fresh install on a second device.
    current_fen TEXT,
    current_uci_history TEXT,
    last_checkpoint_at TIMESTAMP,
    FOREIGN KEY(player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT,
    ply INTEGER,
    fen TEXT,
    uci TEXT,
    san TEXT,
    eval REAL,
    FOREIGN KEY(game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT,
    ply INTEGER,
    explanation_type TEXT,
    confidence REAL,
    learning_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES games(id)
);
