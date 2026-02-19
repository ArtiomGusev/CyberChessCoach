from llm.seca.adaptation.skill_profile import build_skill_profile
from llm.seca.adaptation.teaching_policy import choose_explanation_style
from llm.seca.adaptation.opponent_policy import choose_opponent_parameters


def compute_adaptation(rating: float, confidence: float) -> dict:
    """
    Central adaptive brain of SECA.
    """

    profile = build_skill_profile(rating, confidence)

    teaching = choose_explanation_style(profile)
    opponent = choose_opponent_parameters(profile)

    return {
        "profile": profile,
        "teaching": teaching,
        "opponent": opponent,
    }
