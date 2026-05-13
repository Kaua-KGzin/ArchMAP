---
name: backend-performance-audit
description: Analisa performance backend profundamente e identifica gargalos reais.
---

## Objetivo
Detectar lentidão real e propor melhorias concretas.

## Quando usar
- API lenta
- Alto uso de CPU/memória
- Queries demoradas

## Passos
1. Identificar endpoints críticos
2. Analisar tempo de resposta
3. Verificar queries (N+1, falta de índice)
4. Avaliar uso de memória
5. Identificar gargalos

## Regras
- Priorizar impacto real, não micro-otimização
- Sempre explicar trade-offs

## Output esperado
- Gargalos principais
- Soluções práticas
- Impacto esperado