from __future__ import annotations

import os


def analyze_human(report: dict) -> dict:
    metrics = report.get("metrics", {})
    architecture = report.get("architecture", {})
    health = architecture.get("health") or metrics.get("health") or {}
    score = health.get("score", 100)

    status = "ok"
    if score < 70:
        status = "warning"
    if score < 45:
        status = "critical"

    messages = {
        "ok": "Sua arquitetura parece estar bem estruturada e fácil de manter.",
        "warning": (
            "Atenção: A complexidade do projeto está aumentando "
            "e pode dificultar a manutenção futuramente."
        ),
        "critical": (
            "Cuidado: A arquitetura está em um estado instável. "
            "Mudanças simples podem quebrar o sistema."
        ),
    }

    problems = []
    actions = []

    # 1. Circular dependencies
    cycles = report.get("cycles", [])
    if cycles:
        problems.append("Arquivos dependem uns dos outros em círculo (ovo e galinha).")
        actions.append("Quebre ciclos criando interfaces ou usando eventos.")

    # 2. God modules
    risks = report.get("risks", {})
    god_modules = risks.get("god_modules", [])
    if god_modules:
        problems.append(
            "Alguns arquivos tentam fazer tudo sozinhos, "
            "tornando-se 'arquivos-divindades'."
        )
        actions.append(f"Divida {os.path.basename(god_modules[0]['file'])} em partes menores.")

    # 3. Layer violations
    layer_violations = risks.get("layer_violations", [])
    if layer_violations:
        problems.append(
            "Ocorre uma mistura de camadas "
            "(ex: código de baixo nível conhecendo detalhes da interface)."
        )
        actions.append(
            "Mova lógicas de negócio para o 'Core' e detalhes técnicos "
            "para 'Infra' ou 'Utils'."
        )

    # 4. Dependency explosions
    explosions = risks.get("dependency_explosions", [])
    if explosions:
        problems.append("Alguns arquivos estão conectados a 'quase tudo' no projeto.")
        actions.append("Simplifique os hubs de dependência e reduza o número de imports.")

    # 5. Fallback for healthy projects
    if not problems:
        problems.append("Nenhum grande problema detectado nos padrões atuais.")
        actions.append(
            "Continue seguindo as boas práticas e revise as dependências "
            "ao adicionar novas funcionalidades."
        )

    return {
        "status": status,
        "message": messages.get(status, "Análise concluída."),
        "problems": problems[:3],  # Top 3 problems
        "actions": actions[:3],    # Top 3 actions
        "score": score
    }
