CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    player_id TEXT,
    result TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
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

CREATE TABLE IF NOT EXISTS training_decisions (
    id TEXT PRIMARY KEY,

    player_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,

    -- context snapshot
    rating_before REAL NOT NULL,
    confidence_before REAL NOT NULL,
    recent_accuracy REAL,
    weakness_tactics REAL,
    weakness_time REAL,
    games_last_week INTEGER,

    -- chosen action
    strategy TEXT NOT NULL,

    -- lifecycle
    outcome_ready INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS training_outcomes (
    id TEXT PRIMARY KEY,

    decision_id TEXT NOT NULL,
    measured_at TIMESTAMP NOT NULL,

    rating_after REAL NOT NULL,
    confidence_after REAL NOT NULL,
    games_played INTEGER,

    -- computed reward
    rating_delta REAL NOT NULL,
    confidence_delta REAL NOT NULL,

    FOREIGN KEY(decision_id) REFERENCES training_decisions(id)
);

CREATE INDEX IF NOT EXISTS idx_training_decisions_player
ON training_decisions(player_id);

CREATE INDEX IF NOT EXISTS idx_training_decisions_ready
ON training_decisions(outcome_ready);

CREATE INDEX IF NOT EXISTS idx_training_outcomes_decision
ON training_outcomes(decision_id);
