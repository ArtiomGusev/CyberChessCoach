import sqlite3
import json
import numpy as np

from ..bandit.actions import ACTIONS

DB_PATH = "data/seca.db"


def _action_name(action):
    if isinstance(action, (list, tuple)) and action:
        return str(action[0])
    return str(action)


_ACTION_INDEX = {_action_name(a): i for i, a in enumerate(ACTIONS)}


def _coerce_action(action):
    if isinstance(action, (int, np.integer)):
        return int(action)
    if isinstance(action, str):
        try:
            return int(action)
        except ValueError:
            return _ACTION_INDEX.get(action, 0)
    return 0


def load_training_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT context_json, action_index, reward
            FROM bandit_experiences
            ORDER BY created_at ASC
        """
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        cur.execute(
            """
            SELECT context_json, action, reward
            FROM bandit_experiences
            ORDER BY created_at ASC
        """
        )
        rows = cur.fetchall()

    X, A, y = [], [], []

    for ctx, action, reward in rows:
        X.append(np.array(json.loads(ctx), dtype=float))
        A.append(_coerce_action(action))
        y.append(float(reward))

    conn.close()
    return np.array(X), np.array(A), np.array(y)
