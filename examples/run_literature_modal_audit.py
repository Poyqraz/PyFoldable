"""Use published experimental modal summaries without inventing measured angles."""
from pathlib import Path
import hashlib
import json


def build_modal_audit():
    path = Path(__file__).resolve().parents[1] / "data/literature/measurement_sources.json"
    raw = path.read_bytes()
    registry = json.loads(raw)
    source = next(s for s in registry["sources"] if s["id"] == "yang_2022_hinge_identification_v1")
    inertia = source["reported_rig_inertia_kg_m2"]
    hinge_count = source["reported_rig_hinge_count"]
    rows = []
    for test, frequency, omega_n, zeta, published_damping in source["published_modal_rows"]:
        system_damping = 2 * inertia * omega_n * zeta
        per_hinge = system_damping / hinge_count
        rows.append({
            "published_test_number": test, "frequency_hz": frequency,
            "natural_frequency_rad_s": omega_n, "damping_ratio": zeta,
            "system_modal_damping_nm_s_rad": system_damping,
            "per_hinge_damping_nm_s_rad": per_hinge,
            "published_per_hinge_damping_nm_s_rad": published_damping,
            "rounding_residual_nm_s_rad": per_hinge - published_damping,
            "effective_modal_stiffness_nm_rad": inertia * omega_n**2,
        })
    return {
        "source_doi": source["article_doi"], "source_table": "Table 1",
        "registry_sha256": hashlib.sha256(raw).hexdigest(),
        "classification": "published_experimental_modal_summary_audit",
        "physical_qualification": False, "prototype_parameters_changed": False,
        "angle_time_series_available": False, "reserved_holdout_available": False,
        "effective_modal_stiffness_is_measured_spring_stiffness": False,
        "four_springs_quasistatic_stiffness_nm_rad": hinge_count * source["reported_quasi_static_spring_slopes_nm_rad"][0],
        "limitations": [
            "The identified modal stiffness I*omega_n^2 is an effective system quantity, not a measured individual spring stiffness.",
            "Per-hinge damping is derived from four hinges in parallel; published rows are rounded summaries.",
            "No raw acceleration, observed angle, uncertainty interval, fitting or prototype validation is generated.",
        ], "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(build_modal_audit(), indent=2, sort_keys=True, allow_nan=False))
