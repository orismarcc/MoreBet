"""
Serviço de análise (à parte) — busca de VALOR em mercados 1X2 / mandante /
favorito / dupla chance / handicap, com odds reais, nas mesmas 3 ligas.

Responde, com dados reais (football-data.co.uk, Pinnacle fechamento + Bet365):
  A) Mandante e favorito: dá lucro apostar no mando? e no favorito?
  B) Viés favorito-azarão (favourite-longshot bias) por faixa de odd.
  C) Times de ataque (média de gols alta): apostar na VITÓRIA deles compensa?
     E "vitória ou empate" (dupla chance)? Há relação vitória ↔ over 2.5?
  D) Pente-fino: o modelo bate a linha de fechamento em 1X2? Onde, se em algum
     lugar, existe um segmento sequer empatado (candidato a rentável)?

Metodologia idêntica ao outro serviço: walk-forward (sem vazar futuro), preço
tomado = Bet365, referência de valor/CLV = Pinnacle de fechamento (de-margem).
Uso:  backend/.venv/Scripts/python.exe -m analysis.market_edges
"""
from __future__ import annotations

import csv
import io
import sys
from collections import defaultdict
from dataclasses import dataclass

import httpx

from app.core.engine import TeamInput, analyse_match
from app.core.strength import LeagueAverages
from app.services.football_data import _team_form_averages

LEAGUES = {"E0": "Premier League", "SP1": "La Liga", "D1": "Bundesliga"}
SEASONS = ["2324", "2425", "2526"]
BASE = "https://www.football-data.co.uk/mmz4281"

VALUE_MARGIN = 0.04
ODDS_FLOOR = 1.30
DISAGREEMENT_GUARD = 0.15
MIN_LEAGUE_MATCHES = 30
MIN_TEAM_MATCHES = 5
MIN_SPLIT_MATCHES = 2
FORM_WINDOW = 30
ROLL = 10  # janela p/ média de gols recente do time


@dataclass
class MatchX:
    date: str
    league: str
    home: str
    away: str
    gh: int
    ga: int
    b365h: float | None
    b365d: float | None
    b365a: float | None
    psch: float | None  # Pinnacle closing
    pscd: float | None
    psca: float | None

    @property
    def total(self) -> int:
        return self.gh + self.ga

    @property
    def result(self) -> str:
        return "H" if self.gh > self.ga else ("A" if self.ga > self.gh else "D")


def _f(row, key):
    v = row.get(key, "")
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def _norm_date(d):
    p = d.split("/")
    if len(p) != 3:
        return d
    dd, mm, yy = p
    if len(yy) == 2:
        yy = "20" + yy
    return f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"


def fetch() -> dict[str, list[MatchX]]:
    out = {c: [] for c in LEAGUES}
    with httpx.Client(timeout=30.0, follow_redirects=True) as cl:
        for s in SEASONS:
            for code, name in LEAGUES.items():
                try:
                    r = cl.get(f"{BASE}/{s}/{code}.csv")
                    if r.status_code != 200 or not r.text.strip():
                        continue
                except httpx.HTTPError:
                    continue
                for row in csv.DictReader(io.StringIO(r.text)):
                    gh, ga = _f(row, "FTHG"), _f(row, "FTAG")
                    h, a = row.get("HomeTeam"), row.get("AwayTeam")
                    if gh is None or ga is None or not h or not a:
                        continue
                    out[code].append(MatchX(
                        _norm_date(row.get("Date", "")), name, h, a, int(gh), int(ga),
                        _f(row, "B365H"), _f(row, "B365D"), _f(row, "B365A"),
                        _f(row, "PSCH"), _f(row, "PSCD"), _f(row, "PSCA"),
                    ))
    return out


def demargin3(h, d, a):
    ih, id_, ia = 1 / h, 1 / d, 1 / a
    s = ih + id_ + ia
    return ih / s, id_ / s, ia / s


def roi(profit, n):
    return profit / n * 100 if n else 0.0


# ── A) Mandante e favorito ───────────────────────────────────────────────────
def home_and_favorite(data):
    print("\n" + "=" * 74)
    print("A) MANDANTE E FAVORITO  —  apostar cego dá lucro? (preço Bet365)")
    print("=" * 74)
    for code, name in LEAGUES.items():
        ms = [m for m in data[code] if m.b365h and m.b365d and m.b365a]
        n = len(ms)
        if not n:
            continue
        wh = sum(1 for m in ms if m.result == "H")
        wd = sum(1 for m in ms if m.result == "D")
        wa = sum(1 for m in ms if m.result == "A")
        # apostar sempre no mandante
        home_pl = sum((m.b365h - 1) if m.result == "H" else -1 for m in ms)
        # apostar sempre no favorito (menor odd entre H e A)
        fav_pl = fav_w = 0.0
        for m in ms:
            if m.b365h <= m.b365a:
                fav_pl += (m.b365h - 1) if m.result == "H" else -1
                fav_w += m.result == "H"
            else:
                fav_pl += (m.b365a - 1) if m.result == "A" else -1
                fav_w += m.result == "A"
        print(f"\n{name}  ({n} jogos)")
        print(f"   Resultado: mandante {wh/n*100:4.1f}%  ·  empate {wd/n*100:4.1f}%  ·  visitante {wa/n*100:4.1f}%")
        print(f"   Sempre no MANDANTE : ROI {roi(home_pl,n):+6.2f}%")
        print(f"   Sempre no FAVORITO : ROI {roi(fav_pl,n):+6.2f}%  (acerto {fav_w/n*100:4.1f}%)")


# ── B) Viés favorito-azarão ──────────────────────────────────────────────────
def longshot_bias(data):
    print("\n" + "=" * 74)
    print("B) VIÉS FAVORITO-AZARÃO  —  ROI por faixa de odd (todas as ligas juntas)")
    print("   Aposta no resultado 1X2 ao preço Bet365; agrupa pela odd do palpite.")
    print("=" * 74)
    buckets = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 11.0), (11.0, 999)]
    agg = {b: [0, 0.0, 0] for b in buckets}  # n, profit, wins
    for code in LEAGUES:
        for m in data[code]:
            if not (m.b365h and m.b365d and m.b365a):
                continue
            for odd, hit in (("H", m.result == "H"), ("D", m.result == "D"), ("A", m.result == "A")):
                o = {"H": m.b365h, "D": m.b365d, "A": m.b365a}[odd]
                for b in buckets:
                    if b[0] <= o < b[1]:
                        agg[b][0] += 1
                        agg[b][1] += (o - 1) if hit else -1
                        agg[b][2] += int(hit)
                        break
    print(f"\n   {'faixa de odd':<14}{'apostas':>9}{'acerto':>9}{'ROI':>9}")
    for b in buckets:
        n, pf, w = agg[b]
        if n:
            lbl = f"{b[0]:.1f}–{b[1]:.1f}" if b[1] < 999 else f"{b[0]:.0f}+"
            print(f"   {lbl:<14}{n:>9}{w/n*100:>8.1f}%{roi(pf,n):>+8.2f}%")
    print("\n   Leitura: se favoritos (esq.) perdem MENOS que azarões (dir.), há viés —\n"
          "   mas só vira lucro se alguma faixa ficar ≥ 0.")


# ── C) Times de ataque: vitória e dupla chance ───────────────────────────────
def attacking_teams(data):
    print("\n" + "=" * 74)
    print("C) TIMES DE ATAQUE  —  apostar na vitória de quem faz muito gol compensa?")
    print("   Média de gols MARCADOS do time nos últimos jogos, ANTES da partida.")
    print("=" * 74)

    # Relação vitória ↔ over 2.5 (todas as ligas)
    allm = [m for c in LEAGUES for m in data[c]]
    n = len(allm)
    o25 = sum(1 for m in allm if m.total > 2.5)
    o25_dec = sum(1 for m in allm if m.result != "D" and m.total > 2.5)
    dec = sum(1 for m in allm if m.result != "D")
    o25_draw = sum(1 for m in allm if m.result == "D" and m.total > 2.5)
    draw = sum(1 for m in allm if m.result == "D")
    print(f"\n   Relação vitória ↔ over 2.5  ({n} jogos):")
    print(f"      over 2.5 geral ................. {o25/n*100:4.1f}%")
    print(f"      over 2.5 em jogos DECIDIDOS .... {o25_dec/dec*100:4.1f}%  (alguém venceu)")
    print(f"      over 2.5 em EMPATES ............ {o25_draw/draw*100:4.1f}%")
    print("      → jogo decidido tende a ter mais gol que empate (relação existe, mas é fraca).")

    # Walk-forward: para cada limiar, apostar vitória e (vit ou empate) do time
    # cuja média recente de gols marcados >= limiar.
    for thr in (2.0, 2.5):
        win_n = win_pl = win_w = 0.0
        dc_n = dc_pl = dc_w = 0.0
        for code in LEAGUES:
            scored: dict[str, list[int]] = defaultdict(list)
            for m in data[code]:
                if m.b365h and m.b365d and m.b365a:
                    for team, is_home, mine, odd, draw_odd, won, drew in (
                        (m.home, True, m.gh, m.b365h, m.b365d, m.result == "H", m.result == "D"),
                        (m.away, False, m.ga, m.b365a, m.b365d, m.result == "A", m.result == "D"),
                    ):
                        hist = scored[team]
                        if len(hist) >= MIN_TEAM_MATCHES:
                            avg = sum(hist[-ROLL:]) / len(hist[-ROLL:])
                            if avg >= thr and odd >= ODDS_FLOOR:
                                win_n += 1
                                win_pl += (odd - 1) if won else -1
                                win_w += int(won)
                                dc = 1 / (1 / odd + 1 / draw_odd)  # sintético "time ou empate"
                                dc_n += 1
                                dc_pl += (dc - 1) if (won or drew) else -1
                                dc_w += int(won or drew)
                # registra gols marcados DEPOIS
                scored[m.home].append(m.gh)
                scored[m.away].append(m.ga)
        print(f"\n   Times com média ≥ {thr} gols marcados (janela {ROLL}):")
        if win_n:
            print(f"      VITÓRIA seca   : {int(win_n):>4} apostas · acerto {win_w/win_n*100:4.1f}% · ROI {roi(win_pl,win_n):+6.2f}%")
            print(f"      VIT. ou EMPATE : {int(dc_n):>4} apostas · acerto {dc_w/dc_n*100:4.1f}% · ROI {roi(dc_pl,dc_n):+6.2f}%")
        else:
            print("      (amostra insuficiente — quase nenhum time mantém essa média)")


# ── D) Pente-fino: o modelo bate a linha em 1X2? ─────────────────────────────
def model_value_1x2(data):
    print("\n" + "=" * 74)
    print("D) PENTE-FINO  —  o modelo encontra valor em 1X2 vs fechamento Pinnacle?")
    print("   EV≥4% · odd≥1,30 · guarda 15 p.p. · preço Bet365 · CLV vs Pinnacle close")
    print("=" * 74)
    by_side = defaultdict(lambda: [0, 0.0, 0, 0.0])  # side -> n, profit, wins, clv
    for code, name in LEAGUES.items():
        ms = data[code]
        hist: dict[str, list[dict]] = {}
        n_played = 0
        sh = sa = 0.0
        for m in ms:
            hh, ah = hist.get(m.home, []), hist.get(m.away, [])
            ready = (n_played >= MIN_LEAGUE_MATCHES
                     and len(hh) >= MIN_TEAM_MATCHES and len(ah) >= MIN_TEAM_MATCHES)
            if ready and m.b365h and m.b365d and m.b365a and m.psch and m.pscd and m.psca:
                fh = _team_form_averages(hh, FORM_WINDOW)
                fa = _team_form_averages(ah, FORM_WINDOW)
                if fh["home_played"] >= MIN_SPLIT_MATCHES and fa["away_played"] >= MIN_SPLIT_MATCHES:
                    ti = TeamInput(
                        home_goals_scored_avg=fh["home_goals_scored"],
                        home_goals_conceded_avg=fh["home_goals_conceded"],
                        away_goals_scored_avg=fa["away_goals_scored"],
                        away_goals_conceded_avg=fa["away_goals_conceded"],
                        home_played=fh["home_played"], away_played=fa["away_played"],
                    )
                    league = LeagueAverages(home_goals_avg=sh / n_played, away_goals_avg=sa / n_played)
                    mk = analyse_match(ti, league, xg_weight=0.0).markets
                    sharp = demargin3(m.psch, m.pscd, m.psca)
                    for side, p, odd, close, sp, won in (
                        ("H", mk.home_win, m.b365h, m.psch, sharp[0], m.result == "H"),
                        ("D", mk.draw, m.b365d, m.pscd, sharp[1], m.result == "D"),
                        ("A", mk.away_win, m.b365a, m.psca, sharp[2], m.result == "A"),
                    ):
                        if odd < ODDS_FLOOR or abs(p - sp) > DISAGREEMENT_GUARD:
                            continue
                        if p <= sp or p * odd - 1 < VALUE_MARGIN:
                            continue
                        by_side[side][0] += 1
                        by_side[side][1] += (odd - 1) if won else -1
                        by_side[side][2] += int(won)
                        by_side[side][3] += (odd / close - 1) * 100
            hist.setdefault(m.home, []).append({"is_home": True, "scored": m.gh, "conceded": m.ga})
            hist.setdefault(m.away, []).append({"is_home": False, "scored": m.ga, "conceded": m.gh})
            n_played += 1
            sh += m.gh
            sa += m.ga
    tot_n = sum(v[0] for v in by_side.values())
    tot_pl = sum(v[1] for v in by_side.values())
    tot_clv = sum(v[3] for v in by_side.values())
    print()
    names = {"H": "Mandante", "D": "Empate", "A": "Visitante"}
    for s in ("H", "D", "A"):
        n_, pf, w, clv = by_side[s]
        if n_:
            print(f"   {names[s]:<10} {n_:>4} apostas · acerto {w/n_*100:4.1f}% · ROI {roi(pf,n_):+6.2f}% · CLV {clv/n_:+.2f}%")
    if tot_n:
        print(f"   {'TOTAL':<10} {tot_n:>4} apostas · ROI {roi(tot_pl,tot_n):+6.2f}% · CLV {tot_clv/tot_n:+.2f}%")
    else:
        print("   Nenhuma aposta passou nos filtros — o modelo não vê valor em 1X2 vs o fechamento.")


def main():
    print("Baixando 1X2 + odds reais (football-data.co.uk)…", file=sys.stderr)
    data = fetch()
    total = sum(len(v) for v in data.values())
    if not total:
        print("Falha ao baixar.", file=sys.stderr)
        return
    print(f"OK: {total} jogos.", file=sys.stderr)
    home_and_favorite(data)
    longshot_bias(data)
    attacking_teams(data)
    model_value_1x2(data)
    print("\n" + "=" * 74)
    print("Tudo a preço Bet365 (tomado) vs Pinnacle fechamento (referência). ROI ≥ 0")
    print("em alguma linha = candidato real; negativo em tudo = mercado eficiente.")
    print("=" * 74)


if __name__ == "__main__":
    main()
