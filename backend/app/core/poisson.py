import math
from dataclasses import dataclass


@dataclass
class PoissonResult:
    probabilities: list[float]  # P(0), P(1), P(2), ... P(max_goals)
    lambda_: float
    max_goals: int

    def prob(self, goals: int) -> float:
        if goals < 0 or goals > self.max_goals:
            return 0.0
        return self.probabilities[goals]

    def prob_at_least(self, goals: int) -> float:
        return sum(self.probabilities[goals:])

    def prob_at_most(self, goals: int) -> float:
        return sum(self.probabilities[: goals + 1])


def poisson_pmf(lambda_: float, k: int) -> float:
    """P(X=k) for Poisson distribution with mean lambda_."""
    if lambda_ <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lambda_) * (lambda_ ** k) / math.factorial(k)


def compute_distribution(lambda_: float, max_goals: int = 8) -> PoissonResult:
    """Compute full Poisson distribution up to max_goals."""
    probs = [poisson_pmf(lambda_, k) for k in range(max_goals + 1)]
    # Normalise residual probability into the last bucket to ensure sum = 1
    residual = 1.0 - sum(probs)
    probs[-1] += residual
    return PoissonResult(probabilities=probs, lambda_=lambda_, max_goals=max_goals)
