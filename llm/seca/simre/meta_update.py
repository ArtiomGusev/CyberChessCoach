# seca/simre/meta_update.py


def choose_winner(mean_A, mean_B, threshold=5):
    """
    Accept new policy only if clearly better.
    """
    if mean_B > mean_A + threshold:
        return "new"
    return "base"
