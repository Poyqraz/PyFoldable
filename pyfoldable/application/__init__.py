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
from .evidence_import import (
    EvidenceImportArtifact,
    EvidenceImportError,
    inspect_evidence_upload,
)
from .folding_mechanism import (
    MechanismGeometryAudit,
    MechanismGeometryInputs,
    MechanismPhysicsFixture,
    MechanismPhysicsPoint,
    build_mechanism_geometry_audit,
    build_mechanism_physics_fixture,
)
from .opening_sensitivity import (
    OpeningSensitivityError,
    OpeningSensitivityRow,
    OpeningSensitivitySnapshot,
    load_opening_sensitivity,
)
from .measurement_comparison import (
    MAX_COMPARISON_JSON_BYTES,
    MEASUREMENT_COMPARISON_REPORT_SCHEMA_VERSION,
    MeasurementComparisonReportArtifact,
    MeasurementComparisonRequest,
    MeasurementComparisonServiceError,
    load_measurement_comparison_json,
    prepare_measurement_comparison_report,
    run_measurement_comparison_report,
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
    "EvidenceImportArtifact",
    "EvidenceImportError",
    "inspect_evidence_upload",
    "MechanismGeometryAudit",
    "MechanismGeometryInputs",
    "MechanismPhysicsFixture",
    "MechanismPhysicsPoint",
    "build_mechanism_geometry_audit",
    "build_mechanism_physics_fixture",
    "OpeningSensitivityError",
    "OpeningSensitivityRow",
    "OpeningSensitivitySnapshot",
    "load_opening_sensitivity",
    "MAX_COMPARISON_JSON_BYTES",
    "MEASUREMENT_COMPARISON_REPORT_SCHEMA_VERSION",
    "MeasurementComparisonReportArtifact",
    "MeasurementComparisonRequest",
    "MeasurementComparisonServiceError",
    "load_measurement_comparison_json",
    "prepare_measurement_comparison_report",
    "run_measurement_comparison_report",
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
