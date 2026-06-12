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
    min_bookie_odds: float   # only bet if the bookie pays MORE than this
    confidence: Confidence
    rationale: str
    caveats: list[str]


class RecommendationReport(BaseModel):
    no_bet: bool
    summary: str
    recommendations: list[ValidatedRecommendation]
    data_quality_notes: list[str]
    model_id: str
    cached: bool = False


SYSTEM_PROMPT = """\
Você é um analista quantitativo de apostas esportivas do MoreBet. Sua função é \
interpretar o dossiê JSON de um confronto de futebol e recomendar os mercados \
mais sólidos — ou recomendar NÃO apostar.

O dossiê contém:
- model: probabilidades calculadas por um modelo Poisson/Dixon-Coles calibrado \
(regressão à média + decaimento de forma). São a FONTE DA VERDADE quantitativa.
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
4. Recomende no MÁXIMO 3 mercados, sempre usando a chave exata de \
model.markets (ex.: "home_or_draw", "under_35", "btts_no").
5. Critérios de confiança (teto rígido — na dúvida, rebaixe):
   - "alta": probabilidade ≥ 0.65 E amostra relevante ≥ 8 jogos E forma/H2H \
não contradizem o modelo E backtest da liga com skill positivo.
   - "media": probabilidade ≥ 0.55 com sinais mistos ou amostra menor.
   - "baixa": todo o resto. Prefira nem recomendar.
6. Se o backtest mostrar skill fraco/negativo em over/btts, trate esses \
mercados com ceticismo explícito e rebaixe a confiança neles.
7. no_bet = true quando nenhum mercado tem probabilidade ≥ 0.55 com suporte \
qualitativo, ou quando os dados são insuficientes/desatualizados. Dizer "não \
aposte" é uma resposta valiosa — não force recomendação.
8. Mercados com margem de segurança (dupla chance, under/over de linha \
distante) merecem preferência quando a confiança é média.
9. data_quality_notes: registre amostras pequenas, dados velhos (> 24h), H2H \
vazio, divergência forte entre forma e modelo.
10. Escreva em português do Brasil, tom direto e profissional. Nunca prometa \
lucro; apostas envolvem risco.\
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
    if len(recs) > 3:
        notes.append(f"Agente sugeriu {len(recs)} mercados; limitado aos 3 primeiros.")
        recs = recs[:3]

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
        validated.append(ValidatedRecommendation(
            market=rec.market,
            market_label=MARKET_LABELS.get(rec.market, rec.market),
            model_probability=round(prob, 4),
            fair_odds=fair,
            min_bookie_odds=fair,
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
