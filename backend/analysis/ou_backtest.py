"""
Serviço de análise (à parte) — lucratividade dos mercados Over/Under 1.5 e 2.5
gols na Premier League, La Liga e Bundesliga, time a time.

Por que este desenho:
- "Lucro" em aposta exige ODDS. Frequência histórica sozinha não diz se há
  lucro — o mercado conhece a mesma história. Então usamos ODDS REAIS de
  fechamento da Pinnacle (a linha mais afiada do mundo) + Bet365, das planilhas
  públicas e gratuitas da football-data.co.uk (resultado + odds por jogo).
- O mercado líquido histórico de gols é o 2.5. Para o 2.5 fazemos o backtest
  COMPLETO de valor (modelo vs linha, P&L real numa banca de R$1000 com a
  estratégia já definida). Para o 1.5 (sem odds de mercado na base) entregamos
  frequência + odd de equilíbrio (break-even), que é o máximo honesto possível.
- Walk-forward: cada jogo é previsto SÓ com os jogos anteriores (sem vazar o
  futuro), exatamente como o app prevê na vida real.

Estratégia já definida (idêntica ao agente do app):
  margem de valor mínima 4% de EV · odd mínima 1,30 · Kelly fracionário (1/4) ·
  teto de 2,5% da banca por aposta · guarda de divergência (descarta se o modelo
  diverge > 15 p.p. da linha afiada — provável erro do modelo, não valor).

Fonte de dados: https://www.football-data.co.uk (dados públicos e gratuitos).
Uso:  backend/.venv/Scripts/python.exe -m analysis.ou_backtest
"""
from __future__ import annotations

import csv
import io
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import httpx

from app.core.engine import TeamInput, analyse_match
from app.core.strength import LeagueAverages
from app.services.football_data import _team_form_averages

# ── Configuração ─────────────────────────────────────────────────────────────
LEAGUES = {"E0": "Premier League", "SP1": "La Liga", "D1": "Bundesliga"}
SEASONS = ["2324", "2425", "2526"]  # 3 temporadas completas mais recentes
BASE = "https://www.football-data.co.uk/mmz4281"

BANKROLL_0 = 1000.0
VALUE_MARGIN = 0.04     # EV mínimo na odd tomada
ODDS_FLOOR = 1.30       # odd mínima
KELLY_FRACTION = 0.25   # Kelly/4
STAKE_CAP = 0.025       # teto 2,5% da banca
DISAGREEMENT_GUARD = 0.15  # descarta divergência grosseira modelo×linha afiada

# Mesmos cortes de amostra do backtest do app
MIN_LEAGUE_MATCHES = 30
MIN_TEAM_MATCHES = 5
MIN_SPLIT_MATCHES = 2
FORM_WINDOW = 30
MIN_BETS_PER_TEAM = 12  # amostra mínima p/ destacar um time como lucrativo


@dataclass
class Match:
    date: str
    home: str
    away: str
    gh: int
    ga: int
    # odds 2.5 (vazio quando a planilha não traz)
    b365_over: float | None
    b365_under: float | None
    pin_close_over: float | None
    pin_close_under: float | None

    @property
    def total(self) -> int:
        return self.gh + self.ga


@dataclass
class Bet:
    date: str
    league: str
    home: str
    away: str
    side: str          # "over" | "under"
    odds: float        # preço tomado (Bet365)
    model_p: float
    sharp_p: float     # prob justa da Pinnacle (de-margem)
    close_odds: float  # odd de fechamento Pinnacle (referência de CLV)
    won: bool

    @property
    def clv_pct(self) -> float:
        # Quanto melhor foi o preço tomado vs o fechamento afiado (+ = bom).
        return (self.odds / self.close_odds - 1.0) * 100 if self.close_odds else 0.0


def _f(row: dict, key: str) -> float | None:
    v = row.get(key, "")
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def fetch_matches() -> dict[str, list[Match]]:
    """Baixa e normaliza os jogos por liga, em ordem cronológica."""
    out: dict[str, list[Match]] = {code: [] for code in LEAGUES}
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for season in SEASONS:
            for code in LEAGUES:
                url = f"{BASE}/{season}/{code}.csv"
                try:
                    r = client.get(url)
                    if r.status_code != 200 or not r.text.strip():
                        continue
                except httpx.HTTPError:
                    continue
                reader = csv.DictReader(io.StringIO(r.text))
                rows = []
                for row in reader:
                    gh, ga = _f(row, "FTHG"), _f(row, "FTAG")
                    home, away = row.get("HomeTeam"), row.get("AwayTeam")
                    if gh is None or ga is None or not home or not away:
                        continue
                    rows.append(Match(
                        date=_norm_date(row.get("Date", "")),
                        home=home, away=away, gh=int(gh), ga=int(ga),
                        b365_over=_f(row, "B365>2.5"), b365_under=_f(row, "B365<2.5"),
                        pin_close_over=_f(row, "PC>2.5"), pin_close_under=_f(row, "PC<2.5"),
                    ))
                # A planilha já vem em ordem de data; mantemos a ordem do arquivo.
                out[code].extend(rows)
    return out


def _norm_date(d: str) -> str:
    # dd/mm/yy(yy) -> yyyy-mm-dd (para ordenar a banca única no tempo)
    parts = d.split("/")
    if len(parts) != 3:
        return d
    dd, mm, yy = parts
    if len(yy) == 2:
        yy = "20" + yy
    return f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"


def demargin(odds_a: float, odds_b: float) -> tuple[float, float]:
    """Remove a margem (overround) de um par de odds -> probabilidades justas."""
    ia, ib = 1.0 / odds_a, 1.0 / odds_b
    s = ia + ib
    return ia / s, ib / s


# ── 1. Frequências descritivas (fatos) ──────────────────────────────────────
@dataclass
class TeamFreq:
    played: int = 0
    o15: int = 0
    o25: int = 0

    def add(self, total: int):
        self.played += 1
        if total > 1.5:
            self.o15 += 1
        if total > 2.5:
            self.o25 += 1


def describe(matches_by_league: dict[str, list[Match]]):
    print("\n" + "=" * 72)
    print("1) FREQUÊNCIA REAL DE GOLS  —  fatos, sem odds")
    print("=" * 72)
    for code, name in LEAGUES.items():
        ms = matches_by_league[code]
        if not ms:
            continue
        n = len(ms)
        o15 = sum(1 for m in ms if m.total > 1.5)
        o25 = sum(1 for m in ms if m.total > 2.5)
        avg = sum(m.total for m in ms) / n
        print(f"\n{name}  ({n} jogos, {SEASONS[0][:2]}/{SEASONS[0][2:]}–{SEASONS[-1][:2]}/{SEASONS[-1][2:]})  ·  média {avg:.2f} gols/jogo")
        print(f"   Over 1.5: {o15/n*100:4.1f}%   |   Under 1.5: {(n-o15)/n*100:4.1f}%")
        print(f"   Over 2.5: {o25/n*100:4.1f}%   |   Under 2.5: {(n-o25)/n*100:4.1f}%")
        # break-even (odd de equilíbrio) p/ a aposta plana
        print(f"   Odd de equilíbrio  →  Over 2.5: {n/o25:.2f}  ·  Under 2.5: {n/(n-o25):.2f}"
              f"  ·  Over 1.5: {n/o15:.2f}  ·  Under 1.5: {n/(n-o15):.2f}")


def team_extremes(matches_by_league: dict[str, list[Match]]):
    """Times mais extremos em Over 2.5 (candidatos a mercado/time específico)."""
    print("\n" + "=" * 72)
    print("2) TIMES MAIS EXTREMOS EM GOLS  —  todos os jogos do time (casa+fora)")
    print("=" * 72)
    for code, name in LEAGUES.items():
        ms = matches_by_league[code]
        if not ms:
            continue
        freq: dict[str, TeamFreq] = defaultdict(TeamFreq)
        for m in ms:
            freq[m.home].add(m.total)
            freq[m.away].add(m.total)
        teams = [(t, f) for t, f in freq.items() if f.played >= 25]
        over = sorted(teams, key=lambda x: x[1].o25 / x[1].played, reverse=True)[:3]
        under = sorted(teams, key=lambda x: x[1].o25 / x[1].played)[:3]
        print(f"\n{name}")
        print("   + Over 2.5 (jogos mais movimentados):")
        for t, f in over:
            print(f"      {t:<16} {f.o25/f.played*100:4.1f}% over 2.5  ({f.played} jogos)  →  equilíbrio {f.played/f.o25:.2f}")
        print("   + Under 2.5 (jogos mais travados):")
        for t, f in under:
            u = f.played - f.o25
            print(f"      {t:<16} {u/f.played*100:4.1f}% under 2.5 ({f.played} jogos)  →  equilíbrio {f.played/u:.2f}")


# ── 3. Backtest de valor com odds reais (mercado 2.5) ────────────────────────
def predict_over25(history_home, history_away, league_avgs) -> float | None:
    h = _team_form_averages(history_home, FORM_WINDOW)
    a = _team_form_averages(history_away, FORM_WINDOW)
    if h["home_played"] < MIN_SPLIT_MATCHES or a["away_played"] < MIN_SPLIT_MATCHES:
        return None
    ti = TeamInput(
        home_goals_scored_avg=h["home_goals_scored"],
        home_goals_conceded_avg=h["home_goals_conceded"],
        away_goals_scored_avg=a["away_goals_scored"],
        away_goals_conceded_avg=a["away_goals_conceded"],
        home_played=h["home_played"],
        away_played=a["away_played"],
    )
    league = LeagueAverages(home_goals_avg=league_avgs[0], away_goals_avg=league_avgs[1])
    return analyse_match(ti, league, xg_weight=0.0).markets.over_25


def collect_bets(matches_by_league: dict[str, list[Match]]) -> list[Bet]:
    """Walk-forward por liga; gera as apostas de valor segundo a estratégia."""
    bets: list[Bet] = []
    for code, name in LEAGUES.items():
        ms = matches_by_league[code]
        histories: dict[str, list[dict]] = {}
        n_played = 0
        sum_h = sum_a = 0.0
        for m in ms:
            hh = histories.get(m.home, [])
            ah = histories.get(m.away, [])
            ready = (n_played >= MIN_LEAGUE_MATCHES
                     and len(hh) >= MIN_TEAM_MATCHES and len(ah) >= MIN_TEAM_MATCHES)
            if ready and m.b365_over and m.b365_under and m.pin_close_over and m.pin_close_under:
                p_over = predict_over25(hh, ah, (sum_h / n_played, sum_a / n_played))
                if p_over is not None:
                    sharp_over, sharp_under = demargin(m.pin_close_over, m.pin_close_under)
                    went_over = m.total > 2.5
                    # avalia OVER e UNDER; escolhe o lado com valor (se houver)
                    for side, p, odds, close, sharp_p, won in (
                        ("over", p_over, m.b365_over, m.pin_close_over, sharp_over, went_over),
                        ("under", 1 - p_over, m.b365_under, m.pin_close_under, sharp_under, not went_over),
                    ):
                        if odds < ODDS_FLOOR:
                            continue
                        if abs(p - sharp_p) > DISAGREEMENT_GUARD:
                            continue          # divergência grosseira → provável erro
                        if p <= sharp_p:
                            continue          # sem valor vs linha afiada
                        if p * odds - 1.0 < VALUE_MARGIN:
                            continue          # EV abaixo do mínimo
                        bets.append(Bet(m.date, name, m.home, m.away, side, odds,
                                        p, sharp_p, close, won))
            # registra o resultado DEPOIS de prever (sem vazar futuro)
            histories.setdefault(m.home, []).append({"is_home": True, "scored": m.gh, "conceded": m.ga})
            histories.setdefault(m.away, []).append({"is_home": False, "scored": m.ga, "conceded": m.gh})
            n_played += 1
            sum_h += m.gh
            sum_a += m.ga
    bets.sort(key=lambda b: b.date)
    return bets


def kelly_stake(p: float, odds: float, bankroll: float) -> float:
    b = odds - 1.0
    f = (b * p - (1 - p)) / b
    if f <= 0:
        return 0.0
    return min(KELLY_FRACTION * f, STAKE_CAP) * bankroll


def simulate(bets: list[Bet]):
    print("\n" + "=" * 72)
    print("3) BACKTEST DE VALOR — mercado 2.5, ODDS REAIS (Bet365 tomada, Pinnacle fechamento)")
    print("   Estratégia: EV≥4% · odd≥1,30 · Kelly/4 · teto 2,5% · guarda 15 p.p.")
    print("=" * 72)
    if not bets:
        print("\n   Nenhuma aposta passou nos filtros de valor — o modelo NÃO encontrou\n"
              "   vantagem sistemática sobre a linha de fechamento (mercado eficiente).")
        return

    # Banca única (Kelly, composta) e métrica plana (ROI limpo, 1u por aposta)
    bankroll = BANKROLL_0
    peak = BANKROLL_0
    max_dd = 0.0
    flat_profit = 0.0
    wins = 0
    clv_sum = 0.0
    by_side = defaultdict(lambda: [0, 0.0, 0])      # side -> [n, flat_profit, wins]
    by_league = defaultdict(lambda: [0, 0.0])       # league -> [n, flat_profit]
    by_team = defaultdict(lambda: [0, 0.0, 0])      # team -> [n, flat_profit, wins]

    for b in bets:
        # plana: 1 unidade
        pl = (b.odds - 1.0) if b.won else -1.0
        flat_profit += pl
        wins += int(b.won)
        clv_sum += b.clv_pct
        by_side[b.side][0] += 1
        by_side[b.side][1] += pl
        by_side[b.side][2] += int(b.won)
        by_league[b.league][0] += 1
        by_league[b.league][1] += pl
        for t in (b.home, b.away):
            by_team[t][0] += 1
            by_team[t][1] += pl
            by_team[t][2] += int(b.won)
        # Kelly composto na banca
        stake = kelly_stake(b.model_p, b.odds, bankroll)
        bankroll += stake * (b.odds - 1.0) if b.won else -stake
        peak = max(peak, bankroll)
        max_dd = max(max_dd, (peak - bankroll) / peak)

    n = len(bets)
    roi = flat_profit / n * 100
    print(f"\n   Apostas: {n}  ·  acerto: {wins/n*100:.1f}%  ·  CLV médio: {clv_sum/n:+.2f}%")
    print(f"   ROI (aposta plana, 1u): {roi:+.2f}%   →   lucro de {flat_profit:+.1f} unidades")
    print(f"\n   Banca de R${BANKROLL_0:.0f} com Kelly/4 composto:")
    print(f"      saldo final: R${bankroll:,.2f}   ({(bankroll/BANKROLL_0-1)*100:+.1f}%)   ·   drawdown máx: {max_dd*100:.1f}%")

    print("\n   Por lado do mercado:")
    for side in ("over", "under"):
        ns, pf, w = by_side[side]
        if ns:
            print(f"      {side.upper():<5} {ns:>4} apostas  ·  acerto {w/ns*100:4.1f}%  ·  ROI {pf/ns*100:+6.2f}%")
    print("\n   Por liga:")
    for lg, (ns, pf) in by_league.items():
        if ns:
            print(f"      {lg:<15} {ns:>4} apostas  ·  ROI {pf/ns*100:+6.2f}%")

    # Times específicos lucrativos (amostra mínima)
    ranked = sorted(
        ((t, d) for t, d in by_team.items() if d[0] >= MIN_BETS_PER_TEAM),
        key=lambda x: x[1][1] / x[1][0], reverse=True,
    )
    print(f"\n   Times mais lucrativos de apostar (≥{MIN_BETS_PER_TEAM} apostas nos jogos dele):")
    for t, (ns, pf, w) in ranked[:8]:
        print(f"      {t:<16} {ns:>3} apostas  ·  ROI {pf/ns*100:+6.2f}%  ·  acerto {w/ns*100:4.1f}%")
    if ranked:
        print("   Piores:")
        for t, (ns, pf, w) in ranked[-4:]:
            print(f"      {t:<16} {ns:>3} apostas  ·  ROI {pf/ns*100:+6.2f}%")


def benchmark(matches_by_league: dict[str, list[Match]]):
    """Aposta cega (sempre over / sempre under) na linha afiada — mostra que o
    mercado é eficiente: apostar por instinto/frequência tende a perder a margem."""
    print("\n" + "=" * 72)
    print("4) CONTROLE — apostar CEGO 'sempre over' / 'sempre under' 2.5 (Bet365)")
    print("=" * 72)
    over_pl = under_pl = 0.0
    n = 0
    for ms in matches_by_league.values():
        for m in ms:
            if not (m.b365_over and m.b365_under):
                continue
            n += 1
            went = m.total > 2.5
            over_pl += (m.b365_over - 1.0) if went else -1.0
            under_pl += (m.b365_under - 1.0) if not went else -1.0
    if n:
        print(f"\n   {n} jogos  ·  sempre OVER: ROI {over_pl/n*100:+.2f}%   ·   sempre UNDER: ROI {under_pl/n*100:+.2f}%")
        print("   (Negativo nos dois = não dá p/ lucrar apostando por frequência; é preciso VALOR.)")


def main():
    print("Baixando resultados + odds reais (football-data.co.uk)…", file=sys.stderr)
    matches = fetch_matches()
    total = sum(len(v) for v in matches.values())
    if total == 0:
        print("Falha ao baixar dados.", file=sys.stderr)
        return
    print(f"OK: {total} jogos carregados.", file=sys.stderr)
    describe(matches)
    team_extremes(matches)
    bets = collect_bets(matches)
    simulate(bets)
    benchmark(matches)
    print("\n" + "=" * 72)
    print("Notas honestas: odds líquidas históricas só existem p/ o 2.5 (por isso o")
    print("1.5 fica em frequência/equilíbrio). O preço tomado é Bet365; a linha de")
    print("fechamento Pinnacle é a referência de CLV. Bater o fechamento da Pinnacle")
    print("é o teste mais duro que existe — é o padrão-ouro de aposta de valor.")
    print("=" * 72)


if __name__ == "__main__":
    main()
