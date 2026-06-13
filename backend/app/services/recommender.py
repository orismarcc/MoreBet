"""
Per-matchup recommendation agent (Claude API).

The agent reads a structured dossier — model probabilities, recent form, H2H,
sample sizes, data freshness and the league's backtest quality — and returns
up to 3 recommended markets with confidence levels and rationale in pt-BR.

Anti-hallucination design (three layers):
1. The dossier is the ONLY source of truth: the system prompt forbids any
   outside fact (injuries, news, lineups) and requires citing dossier numbers.
2. The agent never emits numbers we rely on. It only picks market KEYS and
   writes prose; probability and fair odds are attached server-side from our
   own model output, so they can't be hallucinated.
3. `validate_report` re-checks everything in code: unknown market keys are
   dropped, more than 3 recommendations are trimmed, and confidence levels
   that violate the probability/sample-size rules are downgraded.
"""
import time
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

CONFIDENCE_HIGH_MIN_PROB = 0.65
CONFIDENCE_MED_MIN_PROB = 0.55
CONFIDENCE_HIGH_MIN_SAMPLE = 8

# Profit policy. Betting AT fair odds is EV-zero by construction — the fire
# test proved it (-25% ROI settling at fair). Profit requires a margin:
# min_bookie_odds embeds VALUE_MARGIN of edge, so following the number means
# every bet has ≥ +4% EV. Micro-odds rarely clear that bar at real bookies
# (one loss erases 4-5 wins), so fair odds below ODDS_FLOOR can't be "alta".
VALUE_MARGIN = 0.04
ODDS_FLOOR = 1.30
MAX_RECOMMENDATIONS = 2
# Hard bankroll cap — quarter-Kelly already keeps stakes small, but never let a
# single suggestion exceed this fraction of the bankroll (pro discipline).
STAKE_CAP = 0.025

# pt-BR labels for every market key the model exposes.
MARKET_LABELS: dict[str, str] = {
    "home_win": "Vitória do mandante (1)",
    "draw": "Empate (X)",
    "away_win": "Vitória do visitante (2)",
    "home_or_draw": "Dupla chance 1X (mandante ou empate)",
    "away_or_draw": "Dupla chance X2 (visitante ou empate)",
    "home_or_away": "Dupla chance 12 (sem empate)",
    "over_05": "Mais de 0.5 gols",
    "over_15": "Mais de 1.5 gols",
    "over_25": "Mais de 2.5 gols",
    "over_35": "Mais de 3.5 gols",
    "over_45": "Mais de 4.5 gols",
    "under_05": "Menos de 0.5 gols",
    "under_15": "Menos de 1.5 gols",
    "under_25": "Menos de 2.5 gols",
    "under_35": "Menos de 3.5 gols",
    "under_45": "Menos de 4.5 gols",
    "btts_yes": "Ambos marcam — sim",
    "btts_no": "Ambos marcam — não",
    "ah_home_minus_half": "Handicap asiático mandante -0.5",
    "ah_home_minus_one": "Handicap asiático mandante -1.0",
    "ah_home_minus_one_half": "Handicap asiático mandante -1.5",
    "ah_home_plus_half": "Handicap asiático mandante +0.5",
    "ah_away_minus_half": "Handicap asiático visitante -0.5",
    "ah_away_minus_one": "Handicap asiático visitante -1.0",
    "ah_away_minus_one_half": "Handicap asiático visitante -1.5",
    "ah_away_plus_half": "Handicap asiático visitante +0.5",
    "btts_and_over_25": "Ambos marcam + mais de 2.5 gols",
    "btts_and_under_25": "Ambos marcam + menos de 2.5 gols",
    "home_and_over_25": "Mandante vence + mais de 2.5 gols",
    "away_and_over_25": "Visitante vence + mais de 2.5 gols",
    "score_0_1_goals": "Total de 0 ou 1 gol",
    "score_2_3_goals": "Total de 2 ou 3 gols",
    "score_4_plus_goals": "Total de 4+ gols",
}

Confidence = Literal["alta", "media", "baixa"]


# ── Structured output schema (what the agent fills in) ──────────────────────

class AgentRecommendation(BaseModel):
    market: str = Field(description="Chave exata do mercado, ex.: 'home_or_draw'")
    confidence: Confidence
    rationale: str = Field(description="Justificativa em pt-BR citando números do dossiê")
    caveats: list[str] = Field(default_factory=list, description="Ressalvas honestas")


class AgentReport(BaseModel):
    no_bet: bool = Field(description="true quando nenhum mercado merece aposta")
    summary: str = Field(description="Leitura geral do confronto em 2-4 frases, pt-BR")
    recommendations: list[AgentRecommendation] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(
        default_factory=list,
        description="Limitações dos dados que o usuário deve conhecer",
    )


# ── Validated recommendation (what we return to the client) ─────────────────

class ValidatedRecommendation(BaseModel):
    market: str
    market_label: str
    model_probability: float
    fair_odds: float
    min_bookie_odds: float        # fair × (1 + VALUE_MARGIN): bet only above this
    suggested_stake_pct: float    # quarter-Kelly fraction of bankroll at min odds
    confidence: Confidence
    rationale: str
    caveats: list[str]
    # Real market odds (attached server-side from the-odds-api when available).
    market_odds: float | None = None       # best price across bookmakers
    market_bookmaker: str | None = None     # which book offers it
    market_ev_pct: float | None = None      # EV at that price vs our model fair
    has_market_value: bool | None = None    # beats the sharp line (CLV > 0)
    # Sharp (Pinnacle/exchange) de-margined line — the opponent-adjusted truth.
    sharp_prob: float | None = None         # market's implied probability
    clv_pct: float | None = None            # closing-line value: best vs sharp fair
    # True when the model's probability is far above the sharp market's — vs
    # sharp books that almost always means the model is wrong (e.g. World Cup
    # opponent-strength bias), NOT real value.
    market_disagreement: bool | None = None


class MarketOddsEvent(BaseModel):
    home: str
    away: str
    commence_time: str | None = None
    bookmaker_count: int


class RecommendationReport(BaseModel):
    no_bet: bool
    summary: str
    recommendations: list[ValidatedRecommendation]
    data_quality_notes: list[str]
    model_id: str
    cached: bool = False
    # Present when real market odds were located for this matchup.
    market_odds_event: MarketOddsEvent | None = None


SYSTEM_PROMPT = """\
Você é um analista quantitativo de apostas esportivas do MoreBet. Sua função é \
interpretar o dossiê JSON de um confronto de futebol e recomendar os mercados \
mais sólidos — ou recomendar NÃO apostar.

O dossiê contém:
- model: probabilidades do nosso modelo Poisson/Dixon-Coles calibrado \
(regressão à média + decaimento de forma). É a NOSSA estimativa.
- mercado (quando presente): probabilidades implícitas da LINHA AFIADA \
(Pinnacle/exchange) já de-marginada, e o "edge" do modelo em pontos \
percentuais. ESTA é a melhor estimativa de probabilidade disponível: o mercado \
afiado já precifica força do adversário, mando, motivação e lesões. Use-a como \
RÉGUA da realidade.
- form: forma recente real de cada time (resultados, médias, sequência).
- h2h: últimos confrontos diretos (pode estar vazio).
- backtest: qualidade histórica do modelo nesta liga (skill > 0 = modelo \
melhor que apostar na frequência; accuracy = % de acerto do resultado).
- sample: tamanho das amostras e atualidade dos dados.

REGRAS INEGOCIÁVEIS (violação = resposta inútil):
1. Use EXCLUSIVAMENTE informações presentes no dossiê. É PROIBIDO mencionar ou \
presumir lesões, escalações, transferências, clima, arbitragem, motivação, \
notícias ou qualquer fato externo. Você não tem acesso a nada além do dossiê.
2. Não invente números. Todo número citado na justificativa deve existir no \
dossiê (probabilidades, médias, sequências, percentuais).
3. As probabilidades do modelo não são negociáveis: seu papel é cruzá-las com \
forma e H2H para CONFIRMAR ou ENFRAQUECER a confiança — nunca substituí-las \
pela sua intuição.
4. Recomende no MÁXIMO 2 mercados, sempre usando a chave exata de \
model.markets (ex.: "home_or_draw", "under_35", "btts_no"). Menos é mais: uma \
única aposta excelente vale mais que três medianas.
5. Critérios de confiança (teto rígido — na dúvida, rebaixe):
   - "alta": probabilidade ≥ 0.65 E amostra relevante ≥ 8 jogos E forma/H2H \
não contradizem o modelo E backtest da liga com skill positivo. APENAS \
confiança alta é convite a apostar; média e baixa são observação.
   - "media": probabilidade ≥ 0.55 com sinais mistos ou amostra menor.
   - "baixa": todo o resto. Prefira nem recomendar.
6. Se o backtest mostrar skill fraco/negativo em over/btts, trate esses \
mercados com ceticismo explícito e rebaixe a confiança neles.
7. no_bet = true quando nenhum mercado tem probabilidade ≥ 0.55 com suporte \
qualitativo, ou quando os dados são insuficientes/desatualizados. Dizer "não \
aposte" é uma resposta valiosa — não force recomendação. Em teste real, \
seguir recomendações fracas deu prejuízo; abster-se preservou a banca.
8. REGRAS DE LUCRATIVIDADE E VALOR (a pergunta certa é "a odd está errada?", \
não "quem ganha?"):
   - VALOR vem de apostar quando a melhor odd das casas supera a linha afiada \
de fechamento (CLV positivo). A previsão sozinha não gera lucro; o preço sim.
   - Quando o dossiê traz "mercado": só recomende um mercado se o modelo \
estiver ACIMA da probabilidade do mercado afiado (edge_modelo_pp positivo) — \
isso é valor potencial. Se o modelo estiver ABAIXO do mercado, NÃO recomende.
   - Mas desconfie de edge grande demais. Se o modelo estiver MUITO acima do \
mercado afiado (edge > ~15 pp), é quase sempre o MODELO errado, não valor: o \
mercado já pondera força do adversário. Uma sequência de vitórias contra \
adversários fracos NÃO supera a vantagem preditiva de um time forte — o preço \
afiado já sabe disso. Nesses casos, rebaixe a confiança e diga explicitamente \
que há divergência com o mercado.
   - Prefira mercados de MENOR margem: 1X2, Over/Under e Handicap Asiático. \
Evite combos exóticos (resultado+gols) — margem alta, valor raro.
   - Evite odd justa abaixo de ~1.30: micro-odds raramente carregam valor e \
uma derrota apaga várias vitórias. Faixa ideal de odd justa: 1.30–3.00.
   - Entre dois mercados, prefira o de skill positivo no backtest da liga.
9. data_quality_notes: registre amostras pequenas, dados velhos (> 24h), H2H \
vazio, divergência forte entre forma e modelo.
10. Escreva em português do Brasil, tom direto e profissional. Nunca prometa \
lucro; apostas envolvem risco.
11. FORMATAÇÃO DIDÁTICA dos números (regra forte):
   - Probabilidades SEMPRE em porcentagem com no máximo 1 casa: "80%" ou \
"80,2%", NUNCA "0.8019" ou "0,80".
   - NUNCA escreva as chaves técnicas dos mercados (home_win, over_25, \
home_or_draw, away_win etc.). Use o nome em português: "vitória do mandante", \
"mais de 2,5 gols", "dupla chance mandante ou empate".
   - lambda/λ → escreva "gols esperados" (ex.: "3,56 gols esperados do \
mandante"), não "lambda 3.561".
   - Odds com 2 casas (ex.: "1,25"). Edge em pontos percentuais inteiros ou 1 \
casa (ex.: "+27 pp"). Use vírgula decimal (padrão pt-BR).\
"""


# ── In-process result cache (avoid paying for repeated clicks) ──────────────
_CACHE_TTL = 3600.0
_cache: dict[tuple[int, int], tuple[float, RecommendationReport]] = {}


def is_configured() -> bool:
    return bool(settings.anthropic_api_key)


def validate_report(
    report: AgentReport,
    markets: dict[str, float],
    min_sample: int,
    backtest_skill: float | None,
) -> tuple[list[ValidatedRecommendation], list[str]]:
    """Code-level enforcement of the prompt rules. Returns (validated recs,
    audit notes about anything that was dropped or downgraded)."""
    notes: list[str] = []
    validated: list[ValidatedRecommendation] = []

    recs = report.recommendations
    if len(recs) > MAX_RECOMMENDATIONS:
        notes.append(
            f"Agente sugeriu {len(recs)} mercados; limitado aos "
            f"{MAX_RECOMMENDATIONS} primeiros."
        )
        recs = recs[:MAX_RECOMMENDATIONS]

    seen: set[str] = set()
    for rec in recs:
        prob = markets.get(rec.market)
        if prob is None:
            notes.append(f"Mercado desconhecido descartado: '{rec.market}'.")
            continue
        if rec.market in seen:
            continue
        seen.add(rec.market)

        confidence = rec.confidence
        caveats = list(rec.caveats)
        # Hard caps — the model's own probability bounds the agent's confidence.
        if prob < CONFIDENCE_MED_MIN_PROB and confidence != "baixa":
            confidence = "baixa"
            caveats.append("Confiança rebaixada: probabilidade do modelo abaixo de 55%.")
        elif prob < CONFIDENCE_HIGH_MIN_PROB and confidence == "alta":
            confidence = "media"
            caveats.append("Confiança rebaixada: probabilidade do modelo abaixo de 65%.")
        if confidence == "alta" and min_sample < CONFIDENCE_HIGH_MIN_SAMPLE:
            confidence = "media"
            caveats.append(
                f"Confiança rebaixada: amostra de apenas {min_sample} jogos no recorte."
            )
        if confidence == "alta" and backtest_skill is not None and backtest_skill <= 0:
            confidence = "media"
            caveats.append("Confiança rebaixada: backtest da liga sem skill positivo.")

        fair = round(1.0 / max(prob, 1e-6), 3)
        if fair < ODDS_FLOOR and confidence == "alta":
            confidence = "media"
            caveats.append(
                f"Confiança rebaixada: odd justa {fair:.2f} abaixo de {ODDS_FLOOR:.2f} — "
                "micro-odds raramente oferecem valor real e uma derrota apaga várias vitórias."
            )

        # Bet only above this number → every bet carries ≥ VALUE_MARGIN of EV.
        min_odds = round(fair * (1 + VALUE_MARGIN), 3)
        # Quarter-Kelly sized AT the minimum odds (edge = VALUE_MARGIN):
        # kelly = m·p / (1 + m − p)
        kelly = VALUE_MARGIN * prob / max(1 + VALUE_MARGIN - prob, 1e-6)
        validated.append(ValidatedRecommendation(
            market=rec.market,
            market_label=MARKET_LABELS.get(rec.market, rec.market),
            model_probability=round(prob, 4),
            fair_odds=fair,
            min_bookie_odds=min_odds,
            suggested_stake_pct=round(min(kelly / 4, STAKE_CAP), 4),
            confidence=confidence,
            rationale=rec.rationale,
            caveats=caveats,
        ))
    return validated, notes


async def generate_recommendation(
    cache_key: tuple[int, int],
    dossier: dict,
    markets: dict[str, float],
    min_sample: int,
    backtest_skill: float | None,
) -> RecommendationReport:
    if not is_configured():
        raise RuntimeError("ANTHROPIC_API_KEY não configurada")

    hit = _cache.get(cache_key)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        cached = hit[1].model_copy(deep=True)
        cached.cached = True
        return cached

    import json

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                "Analise o confronto descrito no dossiê abaixo e produza o "
                "relatório no formato exigido.\n\n```json\n"
                + json.dumps(dossier, ensure_ascii=False, indent=1)
                + "\n```"
            ),
        }],
        output_format=AgentReport,
    )

    report: AgentReport | None = response.parsed_output
    if report is None:
        raise RuntimeError("Resposta do agente não pôde ser validada contra o schema")

    validated, audit_notes = validate_report(report, markets, min_sample, backtest_skill)

    result = RecommendationReport(
        no_bet=report.no_bet or not validated,
        summary=report.summary,
        recommendations=validated,
        data_quality_notes=report.data_quality_notes + audit_notes,
        model_id=settings.anthropic_model,
    )
    _cache[cache_key] = (time.monotonic(), result)
    if len(_cache) > 200:
        oldest = sorted(_cache.items(), key=lambda kv: kv[1][0])[:50]
        for k, _ in oldest:
            _cache.pop(k, None)
    return result
