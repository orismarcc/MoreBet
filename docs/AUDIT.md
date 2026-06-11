# MoreBet — Auditoria Técnica e Roadmap

> Documento de referência gerado a partir de uma auditoria completa do código
> em `claude/friendly-darwin-0ko45r`. Cada item tem severidade (P0–P3) e
> referência ao arquivo. Itens marcados ✅ foram corrigidos nos commits desta
> branch; itens ⏳ aguardam aprovação / implementação futura.

---

## P0 — Bugs críticos (correção / segurança)

| # | Local | Problema | Status |
|---|-------|----------|--------|
| 1 | `backend/app/main.py` | Credenciais admin hardcoded (`amor1234`) commitadas no repo. | ✅ |
| 2 | `backend/app/services/ingestion.py`, `api_football.py` | `fetch_players` chama API-Football com IDs do football-data.org → toda chamada falha. | ✅ (removido) |
| 3 | `backend/app/services/ingestion.py` | `ingest_players_for_team` definido mas nunca chamado por nenhuma rota. | ✅ (removido) |
| 4 | `backend/app/services/football_data.py` | Sem retry / rate-limit handling; free tier limita 10 req/min e `ingest_all_leagues` faz 16+ requisições. | ✅ |
| 5 | `backend/app/config.py` | JWT secret default permite deploy inseguro silencioso. | ✅ (warning em runtime) |
| 6 | `backend/app/db/database.py` | `create_all()` em vez de Alembic — schema novo não migra em prod. | ⏳ |
| 7 | `backend/app/api/routes/fixtures.py` | Loop sequencial sobre 8 ligas (lento) + `except Exception: continue` silencia erros. | ✅ |
| 8 | `backend/app/api/routes/fixtures.py` | N+1 query no enrichment com IDs do DB. | ✅ |
| 9 | `backend/app/services/api_football.py` | Arquivo legacy não usado, apenas serve `fetch_players` quebrado. | ✅ (removido) |
| 10 | `frontend/src/lib/api.ts` | Token JWT em localStorage → vulnerável a XSS. | ⏳ (precisa cookie HttpOnly + endpoint refresh) |

## P1 — Modelagem matemática

| # | Local | Problema | Status |
|---|-------|----------|--------|
| 11 | `backend/app/core/markets.py` | Mercados limitados: faltam AH ±1, ±1.5, ±2; Over 1.5; gols asiáticos (2.0, 2.25, 2.75); HT/FT; gols time-a-time. | ✅ (parcial — AH ±1/±1.5 + Over/Under 1.5/4.5 + score 0-1/2-3/4+) |
| 12 | `backend/app/core/matrix.py` | Sem correção Dixon-Coles para placares baixos. | ✅ |
| 13 | `backend/app/core/engine.py` | Vantagem de mando só implícita nas médias home/away. Tuning calibrado adicional ausente. | ⏳ |
| 14 | `backend/app/core/engine.py` | `_player_modifier` dupla-conta absences que já estão nas médias do time. | ⏳ (documentado, decisão produto) |
| 15 | `backend/app/services/football_data.py` | `FORM_WINDOW=30` dilui forma recente — sem decaimento exponencial. | ⏳ |
| 16 | `backend/app/core/odds.py` | Sem Kelly Criterion. | ✅ |
| 17 | Sistema todo | Sem integração com bookmakers (Pinnacle, Bet365) para auto-comparar odds. | ⏳ (requer assinatura API the-odds-api ou similar) |

## P2 — UX / Navegação

| # | Local | Problema | Status |
|---|-------|----------|--------|
| 18 | `frontend/src/pages/MatchSelector.tsx` | Selects sem escudos — só texto. | ✅ |
| 19 | `frontend/src/pages/MatchSelector.tsx` | "Atualizar dados" apenas uma liga por vez. | ✅ |
| 20 | `frontend/src/pages/MatchSelector.tsx` | Sem indicador de staleness dos dados. | ✅ |
| 21 | `frontend/src/pages/UpcomingFixtures.tsx` | Sem entrada de odds direto na lista. | ⏳ |
| 22 | `frontend/src/pages/UpcomingFixtures.tsx` | Botão "Sem dados" deveria oferecer "Carregar agora". | ✅ |
| 23 | `frontend/src/pages/AnalysisDashboard.tsx` | Sem histórico nem favoritos. | ⏳ |
| 24 | `frontend/src/components/MarketsGrid.tsx` | Mercados read-only — sem campo de odd inline. | ✅ |
| 25 | `frontend/src/components/ScoreHeatmap.tsx` | Heatmap estoura em telas <360px. | ✅ |
| 26 | App geral | Sem páginas Liga / Time. | ⏳ (Team Detail entregue) |
| 27 | App geral | Sem standings. | ⏳ |
| 28 | App geral | Sem H2H. | ⏳ |
| 29 | App geral | Sem dark/light toggle, sem i18n. | ⏳ (não prioritário) |
| 30 | `frontend/src/pages/Login.tsx` | Sem "esqueci senha" / signup. | ⏳ |

## P3 — Robustez / DX

| # | Item | Status |
|---|------|--------|
| 31 | Sem error boundary React. | ✅ |
| 32 | Sem toast — erros inline. | ✅ |
| 33 | Sem cache HTTP de forma recente. | ⏳ |
| 34 | Sem loading skeletons. | ⏳ |
| 35 | Sem testes frontend. | ⏳ |
| 36 | `vite.config.ts` proxy não documentado. | ⏳ |
| 37 | Sem CI (lint/test). | ⏳ |

---

## Sugestões de páginas adicionais

- **/league/:id** — visão completa de uma liga (standings + jogos recentes + próximos + leader stats).
- **/team/:id** — perfil de time (forma, próximos jogos, médias home/away, jogadores principais).
- **/h2h/:home/:away** — histórico de confrontos.
- **/history** — análises feitas pelo usuário (localStorage + opcional sync no backend).
- **/favorites** — apostas favoritadas + EV tracking ao longo do tempo.

## Sugestões de melhorias de produto

1. **Odds Pinnacle automáticas** (assinatura the-odds-api ~$30/mês) — elimina digitação manual e habilita "scanner de valor" automático na lista de fixtures.
2. **Notificações** quando EV > 5% aparecer em qualquer mercado de jogo favoritado.
3. **Bankroll tracker** — registrar apostas reais, calcular ROI e gráfico de yield.
4. **Modelo Dixon-Coles + Tempo decay** — calibração trimestral.
5. **Modelo de cartões/corner** (Poisson com base em médias separadas).
6. **Exportar análise** (PDF/PNG para compartilhar).
