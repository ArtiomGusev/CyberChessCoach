import sqlite3
import numpy as np
from pathlib import Path

from .contextual_bandit import ContextualBandit as SECAContextualBandit

DB_PATH = "data/seca.db"
MODEL_PATH = Path("llm/seca/brain/bandit/bandit.pkl")


def load_experiences():
    """
    Pull past (context, action, reward) from DB.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT context_json, action, reward
        FROM bandit_experiences
        ORDER BY created_at ASC
    """)

    rows = cur.fetchall()
    conn.close()

    experiences = []
    for ctx_json, action, reward in rows:
        context = np.array(eval(ctx_json), dtype=float)
        experiences.append((context, int(action), reward))

    return experiences


def train_bandit():
    """
    Rebuild bandit from full history.
    """
    experiences = load_experiences()

    bandit = SECAContextualBandit(model_path=MODEL_PATH)

    for context, action, reward in experiences:
        bandit.update(context, action, reward)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    bandit.save()

    print(f"Bandit trained on {len(experiences)} experiences")
