"""ArchMAP Python toolkit.

Public API::

    from archmap import analyze_project, AnalysisResult, ArchMapConfig

    result: AnalysisResult = analyze_project("/path/to/project")
    print(result["metrics"]["architectureHealthScore"])
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from archmap.config import ProjectConfig as ArchMapConfig
from archmap.config import load_project_config
from archmap.core import analyze_project as _analyze_project_impl
from archmap.core.parser import ParsedFile, ParsedProject
from archmap.core.perf.budget import BudgetSource
from archmap.core.perf.progress import Progress
from archmap.types import (
    AnalysisResult,
    ComplexityEntry,
    CouplingFileEntry,
    CouplingMetrics,
    CriticalFileEntry,
    CycleDetail,
    DependencyExplosionEntry,
    EdgeResult,
    Finding,
    GodModuleEntry,
    ImpactResult,
    LayerViolationEntry,
    MetricsResult,
    NodeResult,
    RisksResult,
    RiskThresholds,
    SimpleGraph,
    TopRiskFileEntry,
    UnresolvedImportEntry,
)

__version__ = "1.6.0"


def analyze_project(
    project_path: str | Path,
    parallel: bool | None = None,
    use_cache: bool = True,
    time_budget: float | None = None,
    budget_source: BudgetSource = "cli",
    progress: Progress | None = None,
) -> AnalysisResult:
    """Analyze an ArchMAP project and return a typed result.

    Args:
        project_path: Path to the project root directory.
        parallel: Override parallel parsing. ``None`` uses the project config.
        use_cache: Whether to read/write the incremental parse cache.
        time_budget: Soft limit in seconds for the whole run; ``0`` means no
            limit and ``None`` uses ``[analysis.limits] time_budget_seconds``.
        budget_source: Where an explicit ``time_budget`` came from, reported in
            ``metrics.analysisQuality.budget``.
        progress: Optional progress reporter (default ``None`` = silent).

    Returns:
        :class:`AnalysisResult` with nodes, edges, metrics, cycles, risks,
        architecture analysis, insights, and explanation.
    """
    return cast(
        AnalysisResult,
        _analyze_project_impl(
            project_path,
            parallel=parallel,
            use_cache=use_cache,
            time_budget=time_budget,
            budget_source=budget_source,
            progress=progress,
        ),
    )


__all__ = [
    "__version__",
    # Main entry point
    "analyze_project",
    # Result types
    "AnalysisResult",
    "MetricsResult",
    "NodeResult",
    "EdgeResult",
    "ImpactResult",
    "CycleDetail",
    "RisksResult",
    "Finding",
    "GodModuleEntry",
    "LayerViolationEntry",
    "DependencyExplosionEntry",
    "TopRiskFileEntry",
    "RiskThresholds",
    "ComplexityEntry",
    "CouplingMetrics",
    "CouplingFileEntry",
    "CriticalFileEntry",
    "SimpleGraph",
    "UnresolvedImportEntry",
    # Config
    "ArchMapConfig",
    "load_project_config",
    # Parser types
    "ParsedProject",
    "ParsedFile",
]
