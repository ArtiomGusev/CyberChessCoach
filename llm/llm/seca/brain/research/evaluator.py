import random
from dataclasses import dataclass


@dataclass
class ExperimentResult:
    name: str
    avg_gain: float
    samples: int


class ResearchEvaluator:
    """
    Chooses the best learning algorithm based on real player outcomes.
    """

    def __init__(self):
        self.history: list[ExperimentResult] = []

    def record(self, name: str, gains: list[float]):
        if not gains:
            return

        result = ExperimentResult(
            name=name,
            avg_gain=sum(gains) / len(gains),
            samples=len(gains),
        )
        self.history.append(result)

    def best_algorithm(self) -> str | None:
        if not self.history:
            return None

        return max(self.history, key=lambda r: r.avg_gain).name

    def summary(self):
        return [
            {
                "name": r.name,
                "avg_gain": r.avg_gain,
                "samples": r.samples,
            }
            for r in self.history
        ]
