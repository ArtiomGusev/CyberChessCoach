import re

from rag.llm.run_mode_2 import run_mode_2


class TestLLM:
    def __init__(self, initial: str, rewritten: str):
        self.initial = initial
        self.rewritten = rewritten
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        # If the prompt is a rewrite request, return the rewritten safe text
        if "REWRITE INSTRUCTIONS" in prompt:
            return self.rewritten
        return self.initial


def _assert_sanitized(text: str):
    lower = text.lower()
    assert "checkmate" not in lower, f"Still contains checkmate: {text}"
    assert "mate in" not in lower, f"Still contains 'mate in': {text}"
    assert "stockfish" not in lower, f"Still contains 'stockfish': {text}"
    assert not re.search(r"\b(should|must|needs to|best move)\b", lower), f"Still contains advisory language: {text}"
    assert not re.search(r"\b[bnrqk]?[a-h][1-8]\b", lower), f"Still contains notation: {text}"
    # structural headings/triggers should be removed
    assert not re.search(r"(?im)^\s*(recommended move|example move|plan)[:\s]?.*$", text), f"Still contains heading: {text}"
    assert not re.search(r"(?i)\b(white can|black can|if it|consider)\b", lower), f"Still contains structural phrasing: {text}"


def test_notation_sanitization_cascade():
    # Initial output uses algebraic notation and coordinates
    initial = "After 1. e4 e5 2. Nf3, White's knight on f3 is active and White is better."
    rewritten = "The evaluation indicates a development advantage for White and greater piece activity."

    llm = TestLLM(initial=initial, rewritten=rewritten)

    out = run_mode_2(llm=llm, prompt="PROMPT", case_type="tactical")

    _assert_sanitized(out)
    # At least one generation occurred
    assert len(llm.calls) >= 1


def test_mate_notation_advisory_cascade():
    # Initial output contains stockfish, advisory phrasing, mate claim, and notation
    initial = (
        "Stockfish shows the best move is Qh5 leading to mate in 3. You should play Qh5."
    )
    rewritten = "The evaluation indicates a decisive advantage for White without specifying moves."

    llm = TestLLM(initial=initial, rewritten=rewritten)

    out = run_mode_2(llm=llm, prompt="PROMPT", case_type="tactical")

    _assert_sanitized(out)
    # Either deterministic sanitization or a rewrite should have happened
    assert len(llm.calls) >= 1


def test_structure_advisory_notation_cascade():
    # Initial output contains a forbidden 'Plan' heading, advisory language and coordinates
    initial = (
        "Plan: White can play Qh5 and then 0-0. You should look for this idea."
    )
    rewritten = "The evaluation explains that White's activity and castling options increase pressure on Black's position."

    llm = TestLLM(initial=initial, rewritten=rewritten)

    out = run_mode_2(llm=llm, prompt="PROMPT", case_type="tactical")

    _assert_sanitized(out)
    assert len(llm.calls) >= 1
