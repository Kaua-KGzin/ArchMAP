---
name: ArchMAP v0.6.x — Concluído, v0.7.0 — Pronto para iniciar
description: Estado atual de implementação: o que foi feito e o que está pendente por release
type: project
---

## v0.6.x — CONCLUÍDO (commit 70a8897)

Tudo implementado e testado:

- `args.py`: 100% cobertura ✅ — `--quiet` flag adicionado ao analyze
- `reporting.py`: 100% cobertura ✅
- `commands.py`: 99% cobertura — `quiet` suprime banner/insights/hint; detecta `CI=true`
- `main.py`: 95% cobertura
- `server.py`: 85% cobertura + **security hardening**:
  - `POST /api/project` valida que path é diretório existente (400 se não for)
  - `POST /api/reanalyze` rate-limited a 1 req/2s (responde 429 se exceder)
  - `end_headers` override adiciona `X-Content-Type-Options: nosniff` + `X-Frame-Options: SAMEORIGIN`

278 testes passando, linter limpo.

---

## v0.7.0 — PENDENTE (próximo passo)

Ordem de implementação recomendada (por impacto × esforço):

### 1. SARIF exporter (baixo esforço, alto impacto) ← COMEÇAR AQUI
- Novo arquivo: `src/archmap/exporters/sarif_exporter.py`
- Rules ARCH001 (cycles), ARCH002 (layer violations), ARCH003 (god modules), ARCH004 (dep explosions), ARCH005 (custom rules), ARCH006 (health)
- CLI: `archmap analyze --out-sarif archmap.sarif` via novo flag `--out-sarif` em `args.py`
- `reporting.py`: extend `export_outputs` para incluir campo `sarifPath`
- `commands.py`: passar `out_sarif=getattr(args, "out_sarif", None)` para `export_outputs`
- Exporters `__init__.py`: re-export `export_graph_as_sarif`
- Testes: `tests/test_sarif_exporter.py`

Estrutura de dados disponíveis no report:
- `report["cycles"]`: `[["a.py", "b.py", "a.py"], ...]`
- `report["risks"]["layer_violations"]`: `[{"source": "...", "target": "...", "sourceLayer": "...", "targetLayer": "..."}]`
- `report["risks"]["god_modules"]`: `[{"file": "...", "outgoing": N}]`
- `report["risks"]["dependency_explosions"]`: `[{"file": "...", "incoming": N, "outgoing": N, "totalConnections": N}]`
- `report["architecture"]["ruleViolations"]`: `[{"source": "...", "target": "...", "message": "...", "kind": "forbid"}]`
- `report["architecture"]["health"]["score"]`: int 0-100
- `report["projectRoot"]`: str (abs path)

### 2. GitHub Action (muito baixo esforço) — logo após SARIF
- `.github/actions/archmap/action.yml`
- Input: `fail-on-cycles` (default: true)
- Steps: `pip install archmap`, `archmap analyze --out-sarif archmap.sarif --fail-on-cycles`, `github/codeql-action/upload-sarif@v3`

### 3. Cache incremental (médio esforço, alto impacto)
- Novo módulo: `src/archmap/core/cache/analysis_cache.py`
- `AnalysisCache(cache_dir: Path, ttl_hours: float = 24.0)`
  - `file_hash(path: Path) -> str`: SHA-256 dos primeiros 64KB do conteúdo
  - `get_cached_parse(file_id: str, content: str) -> ParsedFile | None`: hash do content, lookup em JSON
  - `store_parse(file_id: str, content: str, result: ParsedFile) -> None`
- Integração em `project_parser.py`: em `parse_project`, após carregar source map, checar cache por file
- Novo config em `config.py`:
  ```python
  class AnalysisConfig(TypedDict):
      ...
      cache: bool           # default: True
      cache_dir: str        # default: ".codeatlas/cache"
      cache_ttl_hours: float  # default: 24.0
  ```
- `analyze_project` em `core/__init__.py`: criar `AnalysisCache` se `config["analysis"]["cache"]` for True
- Testes: `tests/test_analysis_cache.py`

### 4. Pre-commit hook integration (baixo esforço)
- `args.py`: adicionar `--with-hooks` ao subparser `init`
- `commands.py` `run_init`: se `--with-hooks`, criar/atualizar `.pre-commit-config.yaml` com hook archmap
- Hook gerado:
  ```yaml
  repos:
    - repo: local
      hooks:
        - id: archmap
          name: ArchMAP architecture check
          entry: archmap analyze --fail-on-cycles --fail-on-layer-violations
          language: python
          pass_filenames: false
          stages: [pre-push]
  ```

### 5. Property-based testing para parsers (baixo esforço)
- `tests/test_parsers_property.py` com `hypothesis`
- Testar que todos os parsers nunca crasham com input arbitrário
- `@given(st.text())` para cada parser language

**Why:** Garante robustez dos parsers antes de expandir para novos idiomas.
**How to apply:** Ao começar sessão nova, verificar estado desse arquivo e continuar de onde parou.
