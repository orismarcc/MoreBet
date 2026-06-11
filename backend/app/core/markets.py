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
    over_45: float
    under_05: float
    under_15: float
    under_25: float
    under_35: float
    under_45: float
    # BTTS
    btts_yes: float
    btts_no: float
    # Asian Handicap — home line
    ah_home_minus_half: float    # home wins by 1+
    ah_home_minus_one: float     # home wins by 2+ (full -1 line, push refunded)
    ah_home_minus_one_half: float  # home wins by 2+
    ah_home_plus_half: float     # home doesn't lose
    # Asian Handicap — away line
    ah_away_minus_half: float    # away wins by 1+
    ah_away_minus_one: float     # away wins by 2+
    ah_away_minus_one_half: float
    ah_away_plus_half: float     # away doesn't lose
    # Combined markets
    btts_and_over_25: float
    btts_and_under_25: float
    home_and_over_25: float
    away_and_over_25: float
    # Correct score ranges
    score_0_1_goals: float       # 0 or 1 goal total
    score_2_3_goals: float       # exactly 2 or 3 goals total
    score_4_plus_goals: float    # 4 or more goals total


def calc_markets(matrix: ScoreMatrix) -> MatchMarkets:
    home_win = draw = away_win = 0.0
    btts_yes = 0.0
    home_by_1plus = home_by_2plus = 0.0
    away_by_1plus = away_by_2plus = 0.0
    btts_and_over25 = btts_and_under25 = 0.0
    home_and_over25 = away_and_over25 = 0.0
    total_goals_probs: dict[int, float] = {}

    for h in range(matrix.max_goals + 1):
        for a in range(matrix.max_goals + 1):
            p = matrix.matrix[h][a]
            total = h + a
            diff = h - a

            if diff > 0:
                home_win += p
            elif diff == 0:
                draw += p
            else:
                away_win += p

            if diff >= 1:
                home_by_1plus += p
            if diff >= 2:
                home_by_2plus += p
            if diff <= -1:
                away_by_1plus += p
            if diff <= -2:
                away_by_2plus += p

            btts = h >= 1 and a >= 1
            if btts:
                btts_yes += p
                if total > 2.5:
                    btts_and_over25 += p
                else:
                    btts_and_under25 += p

            if diff > 0 and total > 2.5:
                home_and_over25 += p
            if diff < 0 and total > 2.5:
                away_and_over25 += p

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
        over_45=over(4.5),
        under_05=under(0.5),
        under_15=under(1.5),
        under_25=under(2.5),
        under_35=under(3.5),
        under_45=under(4.5),
        btts_yes=btts_yes,
        btts_no=1.0 - btts_yes,
        ah_home_minus_half=home_by_1plus,
        ah_home_minus_one=home_by_2plus,         # ties (1-goal win) get refunded — model excludes them
        ah_home_minus_one_half=home_by_2plus,
        ah_home_plus_half=home_win + draw,
        ah_away_minus_half=away_by_1plus,
        ah_away_minus_one=away_by_2plus,
        ah_away_minus_one_half=away_by_2plus,
        ah_away_plus_half=away_win + draw,
        btts_and_over_25=btts_and_over25,
        btts_and_under_25=btts_and_under25,
        home_and_over_25=home_and_over25,
        away_and_over_25=away_and_over25,
        score_0_1_goals=total_goals_probs.get(0, 0.0) + total_goals_probs.get(1, 0.0),
        score_2_3_goals=total_goals_probs.get(2, 0.0) + total_goals_probs.get(3, 0.0),
        score_4_plus_goals=sum(v for k, v in total_goals_probs.items() if k >= 4),
    )
