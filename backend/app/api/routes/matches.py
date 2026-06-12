import functools

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.orm import Team, League
from app.models.schemas import (
    CalculateMatchIn,
    MatchAnalysisOut,
    MarketsOut,
    FairOddsOut,
    ScoreProb,
    TeamOut,
    ValueCheckIn,
    ValueCheckOut,
)
from app.core.backtest import run_backtest
from app.core.engine import TeamInput, analyse_match
from app.core.strength import LeagueAverages
from app.core.odds import calc_value
from app.services import recommender
from app.services import odds_market
from app.services.football_data import (
    FD_LEAGUES,
    fetch_head_to_head,
    fetch_league_finished_matches,
    fetch_team_recent_matches,
)
from app.services.espn import fetch_match_details

router = APIRouter(prefix="/matches", tags=["matches"])


class H2HMatch(BaseModel):
    match_id: int
    date: str
    competition: str | None
    competition_code: str | None
    home_api_id: int
    home_name: str
    home_crest: str | None
    away_api_id: int
    away_name: str
    away_crest: str | None
    home_goals: int
    away_goals: int


class GoalEvent(BaseModel):
    minute: str
    side: str            # "home" | "away"
    player: str | None
    text: str


class StatLabel(BaseModel):
    key: str
    label: str
    suffix: str


class MatchDetails(BaseModel):
    found: bool
    reason: str | None = None
    source: str | None = None
    stat_labels: list[StatLabel] = []
    home_stats: dict[str, str | None] = {}
    away_stats: dict[str, str | None] = {}
    goals: list[GoalEvent] = []


@router.get("/h2h", response_model=list[H2HMatch])
async def head_to_head(
    home_api_id: int = Query(...),
    away_api_id: int = Query(...),
    limit: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Last direct meetings between two teams (provider team api ids)."""
    hint: str | None = None
    team = db.query(Team).filter(Team.api_id == home_api_id).first()
    if team:
        league = db.query(League).filter(League.id == team.league_id).first()
        if league and league.api_id in FD_LEAGUES:
            hint = FD_LEAGUES[league.api_id][0]
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await fetch_head_to_head(
                client, home_api_id, away_api_id, limit, league_hint=hint
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")


@router.get("/details", response_model=MatchDetails)
async def match_details(
    date: str = Query(..., description="ISO datetime of the match"),
    home: str = Query(..., min_length=2, max_length=80),
    away: str = Query(..., min_length=2, max_length=80),
    competition_code: str | None = Query(default=None, max_length=40),
):
    """Detailed statistics (possession, shots, corners, goal timeline) for a
    played match — best effort via the public stats source."""
    return await fetch_match_details(competition_code, date, home, away)


def _player_modifier(absent_players: list, team_total_contribution: float = 1.0) -> float:
    """
    Reduce team attack lambda based on absent players' goal contribution.
    If key player contributed 30% of goals, modifier = 1 - 0.30 = 0.70.
    Minimum modifier capped at 0.50 to avoid extreme values.
    """
    total_impact = sum(p.goal_contribution_pct for p in absent_players)
    return max(1.0 - total_impact, 0.50)


def _run_analysis(payload: CalculateMatchIn, db: Session):
    """Shared by /calculate and /recommend: validates teams/league and runs
    the full model pipeline. Returns (result, home_team, away_team, league,
    home_modifier, away_modifier)."""
    home_team = db.query(Team).filter(Team.id == payload.home_team_id).first()
    away_team = db.query(Team).filter(Team.id == payload.away_team_id).first()

    if not home_team or not away_team:
        raise HTTPException(status_code=404, detail="One or both teams not found")
    if home_team.league_id != away_team.league_id:
        raise HTTPException(
            status_code=400,
            detail="Análise disponível apenas entre times da mesma liga — o modelo "
                   "normaliza as forças pelas médias da liga em comum.",
        )

    league = db.query(League).filter(League.id == home_team.league_id).first()
    if not league or not league.home_goals_avg:
        raise HTTPException(
            status_code=422,
            detail="League averages not available — run a data refresh first",
        )

    home_modifier = _player_modifier(payload.absent_home)
    away_modifier = _player_modifier(payload.absent_away)

    team_input = TeamInput(
        home_goals_scored_avg=home_team.home_goals_scored,
        home_goals_conceded_avg=home_team.home_goals_conceded,
        away_goals_scored_avg=away_team.away_goals_scored,
        away_goals_conceded_avg=away_team.away_goals_conceded,
        home_xg_scored_avg=home_team.home_xg_scored,
        home_xg_conceded_avg=home_team.home_xg_conceded,
        away_xg_scored_avg=away_team.away_xg_scored,
        away_xg_conceded_avg=away_team.away_xg_conceded,
        home_player_modifier=home_modifier,
        away_player_modifier=away_modifier,
        home_played=home_team.home_played,
        away_played=away_team.away_played,
    )

    league_avgs = LeagueAverages(
        home_goals_avg=league.home_goals_avg,
        away_goals_avg=league.away_goals_avg,
        home_xg_avg=league.home_xg_avg,
        away_xg_avg=league.away_xg_avg,
    )

    result = analyse_match(team_input, league_avgs, xg_weight=payload.xg_weight)
    return result, home_team, away_team, league, home_modifier, away_modifier


@router.post("/calculate", response_model=MatchAnalysisOut)
def calculate_match(payload: CalculateMatchIn, db: Session = Depends(get_db)):
    result, home_team, away_team, _league, home_modifier, away_modifier = \
        _run_analysis(payload, db)

    top_scores = [
        ScoreProb(home=h, away=a, prob=round(p, 6))
        for h, a, p in result.top_scores
    ]

    return MatchAnalysisOut(
        lambda_home=round(result.lambda_home, 4),
        lambda_away=round(result.lambda_away, 4),
        home_modifier=home_modifier,
        away_modifier=away_modifier,
        markets=MarketsOut(**result.markets.__dict__),
        fair_odds=FairOddsOut(**result.fair_odds.__dict__),
        top_scores=top_scores,
        home_team=TeamOut.model_validate(home_team),
        away_team=TeamOut.model_validate(away_team),
    )


# Backtest summaries are expensive-ish (provider fetch + full replay); keep a
# small per-league memo so the recommendation flow stays snappy.
import time as _time
_bt_cache: dict[int, tuple[float, dict | None]] = {}
_BT_TTL = 6 * 3600.0


async def _backtest_summary(client: httpx.AsyncClient, league_api_id: int) -> dict | None:
    """Best-effort league backtest summary for the agent dossier."""
    hit = _bt_cache.get(league_api_id)
    if hit and _time.monotonic() - hit[0] < _BT_TTL:
        return hit[1]
    summary: dict | None = None
    try:
        _info, matches = await fetch_league_finished_matches(client, league_api_id)
        bt = run_backtest(matches)
        if bt.n_predicted >= 50:
            summary = {
                "jogos_avaliados": bt.n_predicted,
                "skill_1x2": round(bt.skill_score_1x2, 3) if bt.skill_score_1x2 is not None else None,
                "accuracy_1x2": round(bt.accuracy_model, 3) if bt.accuracy_model is not None else None,
                "accuracy_baseline": round(bt.accuracy_baseline, 3) if bt.accuracy_baseline is not None else None,
                "skill_over25": (
                    round(1 - bt.brier_over25_model / bt.brier_over25_baseline, 3)
                    if bt.brier_over25_model and bt.brier_over25_baseline else None
                ),
                "skill_btts": (
                    round(1 - bt.brier_btts_model / bt.brier_btts_baseline, 3)
                    if bt.brier_btts_model and bt.brier_btts_baseline else None
                ),
            }
    except Exception:  # provider down → agent just won't see backtest context
        pass
    _bt_cache[league_api_id] = (_time.monotonic(), summary)
    return summary


@router.post("/recommend", response_model=recommender.RecommendationReport)
async def recommend_match(payload: CalculateMatchIn, db: Session = Depends(get_db)):
    """Per-matchup AI analyst: builds a grounded dossier (model probabilities,
    recent form, H2H, backtest quality) and asks the recommendation agent for
    up to 3 markets with confidence levels — every number server-validated."""
    if not recommender.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Agente não configurado — defina ANTHROPIC_API_KEY no servidor.",
        )

    result, home_team, away_team, league, home_mod, away_mod = _run_analysis(payload, db)

    markets = {k: round(v, 4) for k, v in result.markets.__dict__.items()}
    hint = FD_LEAGUES[league.api_id][0] if league.api_id in FD_LEAGUES else None

    # Qualitative context — best-effort; the agent must flag what's missing.
    form_home = form_away = None
    h2h: list[dict] = []
    backtest = None
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            form_home = await fetch_team_recent_matches(
                client, home_team.api_id, limit=6, league_hint=hint)
            form_away = await fetch_team_recent_matches(
                client, away_team.api_id, limit=6, league_hint=hint)
            h2h = await fetch_head_to_head(
                client, home_team.api_id, away_team.api_id, limit=5, league_hint=hint)
            backtest = await _backtest_summary(client, league.api_id)
    except httpx.HTTPError:
        pass

    def _form_block(form: dict | None) -> dict | None:
        if not form:
            return None
        s = form["summary"]
        return {
            "sequencia": s["form"],
            "jogos": s["played"],
            "vitorias": s["wins"], "empates": s["draws"], "derrotas": s["losses"],
            "media_gols_pro": s["avg_goals_for"],
            "media_gols_contra": s["avg_goals_against"],
            "pct_over25": s["over_25_pct"],
            "pct_btts": s["btts_pct"],
            "jogos_sem_sofrer": s["clean_sheets"],
            "jogos_sem_marcar": s["failed_to_score"],
            "pontos_por_jogo": s["ppg"],
        }

    dossier = {
        "confronto": {
            "mandante": home_team.name,
            "visitante": away_team.name,
            "liga": league.name,
            "media_gols_mandantes_liga": round(league.home_goals_avg, 3),
            "media_gols_visitantes_liga": round(league.away_goals_avg, 3),
        },
        "model": {
            "lambda_mandante": round(result.lambda_home, 3),
            "lambda_visitante": round(result.lambda_away, 3),
            "modificador_desfalques_mandante": home_mod,
            "modificador_desfalques_visitante": away_mod,
            "markets": markets,
            "placares_mais_provaveis": [
                {"placar": f"{h}-{a}", "prob": round(p, 4)}
                for h, a, p in result.top_scores[:5]
            ],
        },
        "sample": {
            "jogos_mandante_em_casa": home_team.home_played,
            "jogos_visitante_fora": away_team.away_played,
            "dados_atualizados_em": (
                home_team.last_updated.isoformat() if home_team.last_updated else None
            ),
        },
        "form": {
            "mandante": _form_block(form_home),
            "visitante": _form_block(form_away),
        },
        "h2h": [
            {
                "data": m["date"][:10],
                "competicao": m["competition"],
                "placar": f"{m['home_name']} {m['home_goals']}x{m['away_goals']} {m['away_name']}",
            }
            for m in h2h
        ],
        "backtest": backtest,
    }

    min_sample = min(home_team.home_played or 0, away_team.away_played or 0)
    skill = backtest.get("skill_1x2") if backtest else None
    try:
        report = await recommender.generate_recommendation(
            cache_key=(home_team.id, away_team.id),
            dossier=dossier,
            markets=markets,
            min_sample=min_sample,
            backtest_skill=skill,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Falha no agente: {e}")

    # Close the value loop: attach REAL bookmaker odds (the-odds-api) to each
    # recommendation and flag whether the value bar is actually cleared. Done
    # after generation (and on cache hits) so prices stay fresh; best-effort.
    await _attach_market_odds(report, league.api_id, home_team.name, away_team.name)
    return report


async def _attach_market_odds(report, league_api_id: int, home: str, away: str) -> None:
    if not odds_market.is_configured() or not report.recommendations:
        return
    wanted = [r.market for r in report.recommendations]
    try:
        mo = await odds_market.fetch_market_odds(league_api_id, home, away, wanted)
    except Exception:
        return
    if not mo:
        return
    report.market_odds_event = recommender.MarketOddsEvent(**mo["event"])
    for rec in report.recommendations:
        entry = mo["odds"].get(rec.market)
        if not entry:
            continue
        rec.market_odds = entry["odds"]
        rec.market_bookmaker = entry["bookmaker"]
        rec.market_ev_pct = round((entry["odds"] / rec.fair_odds - 1) * 100, 2)
        rec.has_market_value = entry["odds"] >= rec.min_bookie_odds
        # Sharp-market reality check: if our probability sits ≥15 points above
        # what even the best available price implies, the model — not the
        # market — is the outlier. Flag it so the UI doesn't scream "value".
        implied = 1.0 / entry["odds"]
        rec.market_disagreement = (rec.model_probability - implied) > 0.15


@router.post("/value", response_model=ValueCheckOut)
def check_value(payload: ValueCheckIn):
    result = calc_value(payload.market, payload.fair_odds, payload.bookie_odds)
    if result.ev_pct > 5:
        verdict = f"VALOR ENCONTRADO! EV de +{result.ev_pct:.1f}%"
    elif result.ev_pct > 0:
        verdict = f"Valor marginal (+{result.ev_pct:.1f}%). Aposte com cautela."
    elif result.ev_pct == 0:
        verdict = "Odd justa. Sem vantagem matemática."
    else:
        verdict = f"Sem valor. Casa com margem de {abs(result.ev_pct):.1f}%."

    return ValueCheckOut(
        market=result.market,
        fair_odds=result.fair_odds,
        bookie_odds=result.bookie_odds,
        ev_pct=result.ev_pct,
        has_value=result.has_value,
        kelly_pct=result.kelly_pct,
        quarter_kelly_pct=round(result.kelly_pct * 0.25, 4),
        verdict=verdict,
    )
