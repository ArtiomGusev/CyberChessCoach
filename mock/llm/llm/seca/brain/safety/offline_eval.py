import sqlite3
import json
import numpy as np

from llm.seca.brain.neural_policy.policy import NeuralCoach
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


def load_bandit_logs():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT context_json, action_index, reward, prob_logged
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
        rows = [(ctx, action, reward, 1.0) for (ctx, action, reward) in cur.fetchall()]

    conn.close()

    data = []
    for ctx, a, r, p in rows:
        data.append((np.array(json.loads(ctx)), _coerce_action(a), float(r), float(p)))

    return data


def ips_estimate(policy: NeuralCoach):
    data = load_bandit_logs()

    if len(data) < 20:
        return None  # not enough data

    total = 0.0

    for ctx, a, r, p_logged in data:
        # probability new policy would pick same action
        a_new = policy.select_action(ctx)

        pi_new = 1.0 if a_new == a else 0.0

        if p_logged > 0:
            total += (pi_new / p_logged) * r

    return total / len(data)
