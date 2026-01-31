# rag/retriever/rule_matcher.py

def matches_conditions(esv: dict, conditions: dict) -> bool:
    for key, value in conditions.items():
        # Support nested keys like "evaluation.band"
        parts = key.split(".")
        current = esv

        for part in parts:
            if part not in current:
                return False
            current = current[part]

        if isinstance(current, list):
            if value not in current:
                return False
        else:
            if current != value:
                return False

    return True
