# CLAUDE.md — ArchMAP

## Projeto
ArchMAP é uma CLI em Python para análise estática de arquitetura de código usando o algoritmo de Tarjan (SCC).
Stack: Python, pytest, ruff. Releases via PowerShell (`scripts/build-exe.ps1`).

---

## Skills disponíveis

Antes de executar qualquer tarefa, leia a skill correspondente em `.claude/skills/`:

| Situação | Skill |
|---|---|
| Implementar uma feature completa | `build-feature.md` |
| Planejar uma feature backend antes de codar | `plan-backend-feature.md` |
| Criar ou modificar endpoint de API | `generate-api-endpoint.md` |
| Debugar erro ou comportamento inesperado | `debug-code.md` ou `debug-issue.md` |
| Encontrar e corrigir causa raiz de um bug | `fix-bug-root-cause.md` |
| Refatorar código existente | `refactor-code.md` ou `refactor-safely.md` |
| Revisar mudanças antes de commitar | `review-changes.md` |
| Otimizar performance | `optimize-code.md` |
| Escrever ou melhorar testes | `write-tests.md` |
| Desenhar arquitetura de sistema | `design-architecture.md` |
| Definir padrões consistentes de backend | `design-system-backend.md` |
| Auditoria de performance de backend | `backend-performance-audit.md` |
| Organizar componentes de frontend | `component-architecture-frontend.md` |
| Revisar UX/UI | `frontend-ux-review.md` |
| Otimizar queries ou banco de dados | `database-optimizer.md` |
| Analisar logs para encontrar problemas | `logs-investigator.md` |
| Analisar dados e extrair insights | `data-analysis-insight.md` |
| Explorar e entender o codebase | `explore-codebase.md` |
| Explicar como um trecho de código funciona | `explain-code.md` |
| Pensar em impactos sistêmicos de uma mudança | `system-thinking-mode.md` |
| Contexto ficou longo / economizar tokens | `token-optimizer.md` ou `token-echo.md` |

---

## Convenções do projeto

- **Testes**: `python -m pytest`
- **Linting**: `python -m ruff check`
- **Instalação de deps**: `pip install`
- **Build**: `powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1`
- **Commits**: seguir o padrão Conventional Commits (`feat:`, `fix:`, `refactor:`, etc.)
- **Co-author nos commits**: `Co-Authored-By: Claude <noreply@anthropic.com>`

---

## Regras gerais

1. Sempre leia a skill (pasta) correspondente **antes** de começar a tarefa.
2. Prefira mudanças incrementais e seguras — especialmente em parsers e no grafo Tarjan.
3. Ao adicionar features, escreva ou atualize os testes correspondentes.
4. Mantenha cobertura de testes acima de 90%.
5. Mensagens de log e comentários em **inglês**.
