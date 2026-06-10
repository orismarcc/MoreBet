from dataclasses import dataclass, field

from app.core.poisson import compute_distribution

MAX_GOALS = 8


@dataclass
class ScoreMatrix:
    """
    Probability matrix P[home_goals][away_goals] for scores 0..MAX_GOALS x 0..MAX_GOALS.
    """
    lambda_home: float
    lambda_away: float
    matrix: list[list[float]] = field(default_factory=list)
    max_goals: int = MAX_GOALS

    def __post_init__(self) -> None:
        if not self.matrix:
            self._build()

    def _build(self) -> None:
        home_dist = compute_distribution(self.lambda_home, self.max_goals)
        away_dist = compute_distribution(self.lambda_away, self.max_goals)
        self.matrix = [
            [home_dist.prob(h) * away_dist.prob(a) for a in range(self.max_goals + 1)]
            for h in range(self.max_goals + 1)
        ]

    def prob_score(self, home: int, away: int) -> float:
        if home > self.max_goals or away > self.max_goals:
            return 0.0
        return self.matrix[home][away]

    def top_scores(self, n: int = 10) -> list[tuple[int, int, float]]:
        """Return n most likely scores as (home, away, probability)."""
        scores = [
            (h, a, self.matrix[h][a])
            for h in range(self.max_goals + 1)
            for a in range(self.max_goals + 1)
        ]
        return sorted(scores, key=lambda x: x[2], reverse=True)[:n]
