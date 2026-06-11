from dataclasses import dataclass, field

from app.core.poisson import compute_distribution

MAX_GOALS = 8

# Dixon-Coles low-score correlation parameter. Negative ρ pulls probability
# from (1,0) and (0,1) into (0,0) and (1,1) — matching the well-known
# under-prediction of draws by raw bivariate Poisson. -0.10 is the canonical
# starting point in the original 1997 paper for top European leagues.
DC_RHO = -0.10


def _dc_tau(home_goals: int, away_goals: int,
            lambda_home: float, lambda_away: float, rho: float) -> float:
    """Dixon-Coles τ adjustment for the four low-score cells."""
    if home_goals == 0 and away_goals == 0:
        return 1.0 - lambda_home * lambda_away * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + lambda_home * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + lambda_away * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


@dataclass
class ScoreMatrix:
    """
    Probability matrix P[home_goals][away_goals] for scores 0..MAX_GOALS x 0..MAX_GOALS.

    Built from the product of two independent Poisson distributions with the
    Dixon-Coles low-score correction applied to the (0,0), (0,1), (1,0) and
    (1,1) cells, then renormalised so the matrix still sums to 1.
    """
    lambda_home: float
    lambda_away: float
    matrix: list[list[float]] = field(default_factory=list)
    max_goals: int = MAX_GOALS
    rho: float = DC_RHO

    def __post_init__(self) -> None:
        if not self.matrix:
            self._build()

    def _build(self) -> None:
        home_dist = compute_distribution(self.lambda_home, self.max_goals)
        away_dist = compute_distribution(self.lambda_away, self.max_goals)

        raw: list[list[float]] = [
            [
                home_dist.prob(h) * away_dist.prob(a)
                * _dc_tau(h, a, self.lambda_home, self.lambda_away, self.rho)
                for a in range(self.max_goals + 1)
            ]
            for h in range(self.max_goals + 1)
        ]
        # Renormalise so the matrix is a valid probability distribution after
        # the DC tweaks (and the residual mass beyond max_goals).
        total = sum(sum(row) for row in raw)
        if total > 0:
            raw = [[cell / total for cell in row] for row in raw]
        self.matrix = raw

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
