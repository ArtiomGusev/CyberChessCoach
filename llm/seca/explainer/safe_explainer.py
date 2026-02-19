# llm/seca/explainer/safe_explainer.py

from typing import Dict


class SafeExplainer:
    """
    Deterministic explanation engine.
    Uses only structured engine signal.
    No LLM.
    """

    def explain(self, engine_signal: Dict) -> str:
        parts = []

        eval_cp = engine_signal.get("eval_cp")
        best_move = engine_signal.get("best_move")
        mate = engine_signal.get("mate_in")
        blunder = engine_signal.get("blunder_type")
        material = engine_signal.get("material_balance")

        # 1) Evaluation
        if mate:
            parts.append(f"Forced mate in {mate} detected.")
        elif eval_cp is not None:
            score = eval_cp / 100
            if score > 1.5:
                parts.append("Position is clearly winning.")
            elif score > 0.5:
                parts.append("Position is slightly better.")
            elif score > -0.5:
                parts.append("Position is roughly equal.")
            elif score > -1.5:
                parts.append("Position is slightly worse.")
            else:
                parts.append("Position is clearly worse.")

        # 2) Best move
        if best_move:
            parts.append(f"Best move is {best_move}.")

        # 3) Material
        if material:
            parts.append(f"Material balance: {material}.")

        # 4) Blunder info
        if blunder:
            parts.append(f"Move classified as {blunder}.")

        return " ".join(parts)
