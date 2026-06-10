from dataclasses import dataclass

from app.core.matrix import ScoreMatrix


@dataclass
class MatchMarkets:
    # 1X2
    home_win: float
    draw: float
    away_win: float
    # Double chance
    home_or_draw: float
    away_or_draw: float
    home_or_away: float
    # Over / Under goals
    over_05: float
    over_15: float
    over_25: float
    over_35: float
    under_05: float
    under_15: float
    under_25: float
    under_35: float
    # BTTS
    btts_yes: float
    btts_no: float
    # Asian Handicap ±0.5
    ah_home_minus_half: float  # home wins by 1+
    ah_away_minus_half: float  # away wins by 1+


def calc_markets(matrix: ScoreMatrix) -> MatchMarkets:
    home_win = draw = away_win = 0.0
    btts_yes = 0.0
    total_goals_probs: dict[int, float] = {}

    for h in range(matrix.max_goals + 1):
        for a in range(matrix.max_goals + 1):
            p = matrix.matrix[h][a]
            total = h + a

            if h > a:
                home_win += p
            elif h == a:
                draw += p
            else:
                away_win += p

            if h >= 1 and a >= 1:
                btts_yes += p

            total_goals_probs[total] = total_goals_probs.get(total, 0.0) + p

    def over(line: float) -> float:
        return sum(v for k, v in total_goals_probs.items() if k > line)

    def under(line: float) -> float:
        return sum(v for k, v in total_goals_probs.items() if k < line)

    return MatchMarkets(
        home_win=home_win,
        draw=draw,
        away_win=away_win,
        home_or_draw=home_win + draw,
        away_or_draw=away_win + draw,
        home_or_away=home_win + away_win,
        over_05=over(0.5),
        over_15=over(1.5),
        over_25=over(2.5),
        over_35=over(3.5),
        under_05=under(0.5),
        under_15=under(1.5),
        under_25=under(2.5),
        under_35=under(3.5),
        btts_yes=btts_yes,
        btts_no=1.0 - btts_yes,
        ah_home_minus_half=home_win,
        ah_away_minus_half=away_win,
    )
