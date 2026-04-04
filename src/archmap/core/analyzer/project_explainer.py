from __future__ import annotations


def explain_project(nodes: list[dict], edges: list[dict]) -> dict:
    folder_counts = {}
    file_count = 0

    for node in nodes:
        if node.get("type") == "file":
            file_count += 1
            folder = node.get("folder", "")
            if folder:
                parts = folder.split("/")
                for part in parts:
                    clean_part = part.lower().strip()
                    folder_counts[clean_part] = folder_counts.get(clean_part, 0) + 1

    # Pattern Detection
    has_api = any(k in folder_counts for k in ["api", "controllers", "routes", "handlers"])
    has_logic = any(
        k in folder_counts
        for k in ["services", "logic", "use_cases", "app", "application"]
    )
    has_db = any(
        k in folder_counts
        for k in ["db", "database", "models", "repository", "infra", "infrastructure"]
    )
    has_ui = any(
        k in folder_counts
        for k in ["ui", "web", "templates", "static", "components"]
    )
    has_cli = any(k in folder_counts for k in ["cli", "commands", "args"])

    # Architecture Classification
    architecture = "General Project"
    if has_api and has_logic and has_db:
        architecture = "Modular API (Layered)"
    elif has_ui and not has_api:
        architecture = "Web Application"
    elif has_cli and not has_ui:
        architecture = "CLI Tool"

    if "core" in folder_counts or "domain" in folder_counts:
        architecture = "Domain-Driven / Clean Architecture"

    # Narrative Generation
    simple = _generate_simple_narrative(has_api, has_logic, has_db, has_ui, has_cli, file_count)
    technical = _generate_technical_narrative(folder_counts)

    return {
        "simple": simple,
        "technical": technical,
        "architecture": architecture,
        "patterns": {
            "api": has_api,
            "logic": has_logic,
            "database": has_db,
            "ui": has_ui,
            "cli": has_cli
        }
    }


def _generate_simple_narrative(has_api, has_logic, has_db, has_ui, has_cli, file_count) -> str:
    parts = []
    if has_api:
        parts.append("uma API para troca de dados")
    if has_ui:
        parts.append("uma interface visual para usuários")
    if has_cli:
        parts.append("uma ferramenta de linha de comando")

    main_desc = " e ".join(parts) if parts else "um projeto de software"

    analysis = f"Este projeto parece ser {main_desc}. "
    analysis += f"Ele contém {file_count} arquivos organizados em pastas estruturadas. "

    if has_logic and has_db:
        analysis += (
            "A lógica de negócio está separada do armazenamento de dados, "
            "o que é um bom sinal de organização."
        )

    return analysis


def _generate_technical_narrative(folder_counts) -> str:
    mapping = {
        "controllers": "entrada de dados (API/Rotas)",
        "api": "pontos de extremidade da API",
        "services": "regras de negócio e processos",
        "models": "definições de dados",
        "database": "persistência de dados",
        "infra": "detalhes de infraestrutura",
        "core": "o coração do sistema (lógica central)",
        "utils": "ferramentas de apoio",
        "cli": "interface de linha de comando"
    }

    found = []
    for key, desc in mapping.items():
        if key in folder_counts:
            found.append(f"- {key} ({desc})")

    if not found:
        return "Estrutura de pastas personalizada sem padrões comuns detectados."

    return "O projeto está dividido em:\n" + "\n".join(found[:5])
