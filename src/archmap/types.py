"""Stable public types for the ArchMAP Python API."""

from __future__ import annotations

from typing import NotRequired, TypedDict

# ---------------------------------------------------------------------------
# Node / edge types
# ---------------------------------------------------------------------------


class ImpactResult(TypedDict):
    nodeId: str
    impactedFiles: list[str]
    impactCount: int
    risk: str  # "low" | "ok" | "warning" | "critical"


class NodeResult(TypedDict):
    id: str
    label: str
    type: str  # "file" | "package"
    language: NotRequired[str]
    folder: NotRequired[str]
    outgoing: int
    incoming: int
    isCircular: bool
    complexityScore: NotRequired[float]
    complexityImports: NotRequired[int]
    complexityDependents: NotRequired[int]
    complexityConnections: NotRequired[int]
    efferentCoupling: NotRequired[int]
    afferentCoupling: NotRequired[int]
    instability: NotRequired[float]
    impact: NotRequired[ImpactResult]


class EdgeResult(TypedDict):
    id: str
    source: str
    target: str
    isCircular: bool


# ---------------------------------------------------------------------------
# Metrics types
# ---------------------------------------------------------------------------


class ComplexityEntry(TypedDict):
    file: str
    imports: int
    dependents: int
    totalConnections: int
    efferentCoupling: int
    afferentCoupling: int
    instability: float
    score: float


class CouplingFileEntry(TypedDict):
    file: str
    afferentCoupling: int
    efferentCoupling: int
    instability: float


class CouplingMetrics(TypedDict):
    averageInstability: float
    mostStable: list[CouplingFileEntry]
    mostVolatile: list[CouplingFileEntry]


class CriticalFileEntry(TypedDict):
    file: str
    dependents: int


class UnresolvedImportEntry(TypedDict):
    file: str
    specifier: str


class MetricsResult(TypedDict):
    filesAnalyzed: int
    totalDependencies: int
    externalDependencies: int
    circularDependencyCount: int
    resolutionRate: float
    unresolvedImportsTotal: NotRequired[int]
    unresolvedImports: NotRequired[list[UnresolvedImportEntry]]
    complexity: list[ComplexityEntry]
    coupling: CouplingMetrics
    criticalFiles: list[CriticalFileEntry]
    architectureHealthScore: float
    architectureStyle: str
    architectureRuleViolations: int


# ---------------------------------------------------------------------------
# Cycle types
# ---------------------------------------------------------------------------


class CycleDetail(TypedDict):
    cycle: list[str]
    length: int


# ---------------------------------------------------------------------------
# Risk types
# ---------------------------------------------------------------------------


class GodModuleEntry(TypedDict):
    file: str
    outgoing: int


class LayerViolationEntry(TypedDict):
    source: str
    target: str
    sourceLayer: str
    targetLayer: str
    rule: str


class DependencyExplosionEntry(TypedDict):
    file: str
    incoming: int
    outgoing: int
    totalConnections: int


class TopRiskFileEntry(TypedDict):
    file: str
    riskScore: int
    dependents: int
    outgoing: int
    signals: list[str]


class RiskThresholds(TypedDict):
    god_module_min_outgoing: int
    dependency_explosion_min_connections: int


class RisksResult(TypedDict):
    god_modules: list[GodModuleEntry]
    layer_violations: list[LayerViolationEntry]
    dependency_explosions: list[DependencyExplosionEntry]
    top_risk_files: list[TopRiskFileEntry]
    thresholds: RiskThresholds


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


class SimpleGraph(TypedDict):
    nodes: list[str]
    edges: list[list[str]]


class AnalysisResult(TypedDict):
    """Return type of :func:`archmap.analyze_project`.

    All top-level keys are guaranteed stable across minor versions.
    Nested dicts (``architecture``, ``insights``, ``explanation``) may grow
    new keys in minor releases but will never remove existing ones.
    """

    projectRoot: str
    nodes: list[NodeResult]
    edges: list[EdgeResult]
    metrics: MetricsResult
    cycles: list[list[str]]
    cycleDetails: list[CycleDetail]
    risks: RisksResult
    architecture: dict
    insights: dict
    explanation: dict
    simple: SimpleGraph


__all__ = [
    "AnalysisResult",
    "ComplexityEntry",
    "CouplingFileEntry",
    "CouplingMetrics",
    "CriticalFileEntry",
    "CycleDetail",
    "DependencyExplosionEntry",
    "EdgeResult",
    "GodModuleEntry",
    "ImpactResult",
    "LayerViolationEntry",
    "MetricsResult",
    "NodeResult",
    "RiskThresholds",
    "RisksResult",
    "SimpleGraph",
    "TopRiskFileEntry",
    "UnresolvedImportEntry",
]
