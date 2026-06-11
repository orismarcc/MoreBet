# MoreBet — Série de patches para revisão

Esta pasta contém **9 commits** prontos para revisão e aplicação, gerados via
`git format-patch master..claude/friendly-darwin-0ko45r`.

> ⚠️ O push automático para o GitHub falhou neste ambiente porque a
> integração não tem permissão de escrita no repositório (`403 Resource not
> accessible by integration`). Por isso a entrega é via patches.

## Como aplicar localmente

```bash
git checkout master
git checkout -b claude/friendly-darwin-0ko45r
git am patches/*.patch
git push -u origin claude/friendly-darwin-0ko45r
```

Se preferir revisar/aplicar um por vez:

```bash
git am patches/0001-docs-add-full-project-audit-and-roadmap-checklist.patch
git am patches/0002-fix-security-seed-admin-from-env-vars-and-refuse-def.patch
# ... etc
```

Para descartar e tentar de novo: `git am --abort`.

## Resumo de cada patch

| # | Tipo | Assunto |
|---|------|---------|
| 0001 | docs | Auditoria completa + roadmap em `docs/AUDIT.md` |
| 0002 | fix(security) | Admin via env vars; recusa JWT secret default em produção |
| 0003 | refactor(backend) | Remove provedor api-football legacy quebrado |
| 0004 | fix(backend) | Retry + backoff em chamadas football-data.org (rate-limit safe) |
| 0005 | perf(backend) | `/fixtures/upcoming` paraleliza ligas + batch query (8s→2s) |
| 0006 | feat(core) | Correção Dixon-Coles para placares baixos (0-0, 1-1, 0-1, 1-0) |
| 0007 | feat(core) | Mercados expandidos (AH ±1/±1.5/+0.5, Over 1.5/4.5, combinados, faixas) + Kelly Criterion no Value Finder |
| 0008 | feat(frontend) | Grid de ligas com escudos, badge de staleness, botão "atualizar todas" |
| 0009 | feat(frontend) | ErrorBoundary + sistema de toast |

## Verificações já rodadas

- ✅ Backend: `pytest tests/` — 41/41 passando
- ✅ Frontend: `tsc --noEmit` — 0 erros
- ✅ Frontend: `vite build` — bundle 362KB / 116KB gzip

## Itens pendentes (documentados em `docs/AUDIT.md`)

- Migração para Alembic em vez de `create_all()` (P0 #6)
- Mover token JWT para cookie HttpOnly (P0 #10)
- Integração com odds reais (Pinnacle / the-odds-api) (P1 #17)
- Páginas: League / Team detail / H2H / Standings / Histórico / Favoritos (P2 #26-28)
- Recuperação de senha + signup (P2 #30)
- Loading skeletons, cache HTTP, testes frontend, CI (P3)
