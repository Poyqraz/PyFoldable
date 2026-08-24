"""Application-facing view models built on the numerical core."""

from .dashboard import (
    DashboardConfigError,
    DashboardSnapshot,
    EvidenceGate,
    EvidenceState,
    load_dashboard_snapshot,
)
from .design_draft import (
    DesignDraftArtifact,
    DesignDraftInputs,
    DraftUnitSelection,
    build_design_draft,
)
from .opening_sensitivity import (
    OpeningSensitivityError,
    OpeningSensitivityRow,
    OpeningSensitivitySnapshot,
    load_opening_sensitivity,
)
from .analysis_run import (
    ANALYSIS_SERVICE_ID,
    ANALYSIS_SERVICE_VERSION,
    PR06D_ANALYSIS_ID,
    AnalysisRecipe,
    AnalysisRunArtifact,
    AnalysisRunError,
    build_pr06d_opening_sensitivity_report,
    get_analysis_recipe,
    render_pr06d_opening_sensitivity_markdown,
    run_analysis,
)

__all__ = [
    "DashboardConfigError",
    "DashboardSnapshot",
    "EvidenceGate",
    "EvidenceState",
    "load_dashboard_snapshot",
    "DesignDraftArtifact",
    "DesignDraftInputs",
    "DraftUnitSelection",
    "build_design_draft",
    "OpeningSensitivityError",
    "OpeningSensitivityRow",
    "OpeningSensitivitySnapshot",
    "load_opening_sensitivity",
    "ANALYSIS_SERVICE_ID",
    "ANALYSIS_SERVICE_VERSION",
    "PR06D_ANALYSIS_ID",
    "AnalysisRecipe",
    "AnalysisRunArtifact",
    "AnalysisRunError",
    "build_pr06d_opening_sensitivity_report",
    "get_analysis_recipe",
    "render_pr06d_opening_sensitivity_markdown",
    "run_analysis",
]
