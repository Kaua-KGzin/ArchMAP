"""ArchMAP Python toolkit.

Public API::

    from archmap import analyze_project, AnalysisResult, ArchMapConfig

    result: AnalysisResult = analyze_project("/path/to/project")
    print(result["metrics"]["architectureHealthScore"])
"""

from __future__ import annotations

from archmap.config import ProjectConfig as ArchMapConfig
from archmap.config import load_project_config
from archmap.core import analyze_project
from archmap.core.parser import ParsedFile, ParsedProject
from archmap.types import (
    AnalysisResult,
    ComplexityMetrics,
    CouplingMetrics,
    CycleDetail,
    EdgeResult,
    MetricsResult,
    NodeResult,
    RiskEntry,
    SimpleGraph,
)

__version__ = "0.9.0"

__all__ = [
    "__version__",
    # Main entry point
    "analyze_project",
    # Result types
    "AnalysisResult",
    "MetricsResult",
    "NodeResult",
    "EdgeResult",
    "CycleDetail",
    "RiskEntry",
    "ComplexityMetrics",
    "CouplingMetrics",
    "SimpleGraph",
    # Config
    "ArchMapConfig",
    "load_project_config",
    # Parser types
    "ParsedProject",
    "ParsedFile",
]
