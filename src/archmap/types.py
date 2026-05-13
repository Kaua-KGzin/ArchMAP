"""Stable public types for the ArchMAP Python API."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class EdgeResult(TypedDict):
    id: str
    source: str
    target: str
    isCircular: bool


class NodeResult(TypedDict):
    id: str
    label: str
    type: str
    language: NotRequired[str]
    folder: NotRequired[str]
    outgoing: int
    incoming: int
    isCircular: bool
    complexity: NotRequired[float]
    impact: NotRequired[float]


class ComplexityMetrics(TypedDict):
    average: float
    max: float
    stdDev: NotRequired[float]


class CouplingMetrics(TypedDict):
    averageOutgoing: float
    averageIncoming: float
    maxOutgoing: int
    maxIncoming: int


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
    complexity: ComplexityMetrics
    coupling: CouplingMetrics
    criticalFiles: list[str]
    architectureHealthScore: float
    architectureStyle: str
    architectureRuleViolations: int


class CycleDetail(TypedDict):
    cycle: list[str]
    length: int


class RiskEntry(TypedDict):
    type: str
    severity: str
    file: NotRequired[str]
    description: str


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
    risks: list[RiskEntry]
    architecture: dict
    insights: dict
    explanation: dict
    simple: SimpleGraph


__all__ = [
    "AnalysisResult",
    "ComplexityMetrics",
    "CouplingMetrics",
    "CycleDetail",
    "EdgeResult",
    "MetricsResult",
    "NodeResult",
    "RiskEntry",
    "SimpleGraph",
    "UnresolvedImportEntry",
]
