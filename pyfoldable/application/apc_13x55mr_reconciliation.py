"""Public inventory for the APC 13x5.5MR reference and the unread ANSYS draft.

The complete vendor tables remain local and uncommitted. This module records
hashes, definitions, identity differences, and gaps. It does not download
files or run a solver.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any


def _mm(inches: str, *, twice: bool = False) -> str:
    value = Decimal(inches) * Decimal("25.4")
    if twice:
        value *= 2
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
RETRIEVED_AT = "2026-10-16T20:20:43Z"
ANSYS_FILENAME = "Tahir_APC_4000RPM_Haftalik_Rapor_Taslagi1.docx"
ANSYS_EXPECTED_SHA256 = "da6ea5414e49c10b40ff1202712193528b1bdb4b01fe7fde64b2d27ce5b856a3"
TASK_SUPPLIED_CAD_DIAMETER_MM = "329.3519"


def _diameter_mm(length_in: float) -> float:
    return length_in * INCH_TO_MM


def build_apc_13x55mr_reconciliation() -> dict[str, Any]:
    """Return the source-bound reconciliation record."""
    nominal_diameter_mm = _mm("13")
    footer_diameter_mm = _mm("6.47", twice=True)
    last_station_diameter_mm = _mm("6.475", twice=True)
    omega = 4000.0 * 2.0 * math.pi / 60.0
    power_from_rounded_torque_w = 0.108 * omega
    return {
        "schema_version": 1,
        "artifact_class": "apc_13x55mr_ansys_reconciliation",
        "physical_qualification": False,
        "genuine_two_profile_comparison": "UNESTABLISHED",
        "solvers_executed": [],
        "performance_substitution_into_cfd": False,
        "synthetic_apc_202602_fixture_is_manufacturer_data": False,
        "retrieved_at": RETRIEVED_AT,
        "local_retention": {
            "path": "outputs/apc_13x55mr_local/",
            "gitignored": True,
            "committed": False,
            "role": "Original vendor bytes and the full parsed performance table stay local.",
        },
        "ansys_report": {
            "filename": ANSYS_FILENAME,
            "expected_sha256": ANSYS_EXPECTED_SHA256,
            "bytes_present_in_workspace": False,
            "sha256_verified": False,
            "figures_read": False,
            "tables_read": False,
            "task_supplied_cad_diameter_mm": TASK_SUPPLIED_CAD_DIAMETER_MM,
            "task_supplied_cad_diameter_status": (
                "Stated by the reconciliation task. Not read from report bytes."
            ),
        },
        "diameters_mm": {
            "nominal_product": nominal_diameter_mm,
            "pe0_footer_radius_times_two": footer_diameter_mm,
            "pe0_last_station_times_two": last_station_diameter_mm,
            "task_supplied_cad": TASK_SUPPLIED_CAD_DIAMETER_MM,
        },
        "derived_checks": {
            "omega_4000_rpm_rad_s": omega,
            "power_w_from_published_torque_0_108_Nm": power_from_rounded_torque_w,
            "published_power_w": 45.403,
            "rounded_torque_reproduces_published_power": False,
        },
        "sources": _sources(),
        "model_separation": _models(),
        "performance_inventory": _performance(),
        "published_4000_rpm_static_row": _static_row(),
        "gap_matrix": _gaps(),
        "engineer_handoff": _handoff(),
        "next_step": _next_step(),
    }


def _sources() -> list[dict[str, Any]]:
    return [
        {
            "role": "performance_index",
            "url": "https://www.apcprop.com/technical-information/performance-data/",
            "retrieved_at": RETRIEVED_AT,
            "statement": (
                "APC generates these files with proprietary vortex-theory software "
                "from propeller geometry. Wind-tunnel data are identified separately "
                "as the UIUC site."
            ),
        },
        {
            "role": "engineering_method",
            "url": "https://www.apcprop.com/technical-information/engineering/",
            "retrieved_at": RETRIEVED_AT,
            "statement": (
                "Performance files estimate thrust, torque, and efficiency. "
                "Lift-drag inputs may be NASA TAIR, polar diagrams, or empirical "
                "minimum-drag notes. In-flight RPM and airspeed measurements are a "
                "separate design-evaluation practice, not this performance file."
            ),
        },
        {
            "role": "download_index",
            "url": "https://www.apcprop.com/technical-information/file-downloads/",
            "retrieved_at": RETRIEVED_AT,
        },
        {
            "role": "geometry_archive",
            "url": "https://www.apcprop.com/wp-content/uploads/2026/02/PE0-FILES_WEB-202602.zipx",
            "sha256": "85a97375dd9ffaeb38022cef1b5d79ac86c56f2960e9917369ad0e55ce37df38",
            "bytes": 1232376,
            "member": "PE0-FILES_WEB/13x55MR-PERF.PE0",
            "member_sha256": "2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f",
            "member_bytes": 11389,
            "internal_version": "v2025-1001",
            "simulation_date": "2026-02-24",
            "matches_existing_public_pin": True,
        },
        {
            "role": "performance_archive",
            "url": "https://www.apcprop.com/wp-content/uploads/2026/02/PERFILES_WEB-202602.zipx",
            "sha256": "fdeaee160617b4006c6a96335050091af4349a1dd33362a1b1b6e74dfa77561f",
            "bytes": 8275714,
            "member": "PERFILES_WEB/PERFILES2/PER3_13x55MR.dat",
            "member_sha256": "bcf3914a4f7ac4c843823d6b9ebf26120824f2052ed145e03a1dad8246ec9751",
        },
        {
            "role": "performance_file",
            "url": "https://www.apcprop.com/files/PER3_13x55MR.dat",
            "sha256": "bcf3914a4f7ac4c843823d6b9ebf26120824f2052ed145e03a1dad8246ec9751",
            "bytes": 117936,
            "internal_version": "v2022-0915",
            "simulation_date": "2022-09-22",
            "airfoil_aero_data": "POLAR DIAGRAMS",
            "identical_to_202602_archive_member": True,
        },
        {
            "role": "technical_workbook",
            "url": "https://www.apcprop.com/wp-content/uploads/2026/02/PROP-DATA-FILE_202602.xlsx",
            "sha256": "4c0dd96f7cb04db95d721a11123fb2ed47956dfa136138a8062d5ee9b4aeb8f2",
            "bytes": 366609,
            "workbook_modified": "2026-02-20T22:24:27Z",
        },
        {
            "role": "adjacent_model_performance_file",
            "model": "13x5.5E",
            "url": "https://www.apcprop.com/files/PER3_13x55E.dat",
            "sha256": "844645069d1457a2f68a5c2ad395a6c33095c7eb0bee0a0f61ba16085d3d0772",
            "internal_version": "v2022-0915",
            "simulation_date": "2022-09-22",
        },
        {
            "role": "adjacent_model_performance_file",
            "model": "13x5.5MRF-RH",
            "url": "https://www.apcprop.com/files/PER3_13x55MRF-RH.dat",
            "sha256": "d96a0e074b7b8cbe070de1dba770bd73aba07aede75892fd74eb4371d6ab895e",
            "archive_member_sha256": "20deb3ffd1aa7c8ef44d48e5389094f6e5db9f5450fba6272ec1766e1e3489dd",
            "stripped_text_matches_archive_member": True,
            "internal_version": "v2022-0915",
            "simulation_date": "2023-03-31",
        },
    ]


def _models() -> list[dict[str, Any]]:
    return [
        {
            "name": "13x5.5MR",
            "sku": "LP13055MR",
            "kind": "fixed multi-rotor",
            "catalog_hub_diameter": "0.65 in.",
            "catalog_weight_text": "0.85 oz.",
            "catalog_weight_lb": 0.0529,
            "catalog_weight_g": 23.994911,
            "pe0_hub_radius_in": 0.32,
            "pe0_hub_diameter_in": 0.64,
            "pe0_weight_lb": 0.054915,
            "pe0_weight_kg": 0.024905,
            "selected_for_this_reconciliation": True,
        },
        {
            "name": "13x5.5E",
            "sku": "LP13055E",
            "kind": "thin electric",
            "catalog_hub_diameter": "0.80 in.",
            "catalog_weight_text": "1.13 oz.",
            "pe0_hub_radius_m": 0.01016,
            "selected_for_this_reconciliation": False,
        },
        {
            "name": "13x5.5MRP",
            "sku": "LP13055MRP",
            "kind": "multi-rotor pusher, reverse rotation",
            "selected_for_this_reconciliation": False,
        },
        {
            "name": "13x5.5MRF-L(B)",
            "sku": "LP13055MRF-L(B)",
            "kind": "folding blades, left-hand, hub not included",
            "catalog_weight_text": "0.78 oz.",
            "selected_for_this_reconciliation": False,
        },
        {
            "name": "13x5.5MRF-R(B)",
            "sku": "LP13055MRF-R(B)",
            "kind": "folding blades, right-hand, hub not included",
            "catalog_weight_text": "0.78 oz.",
            "selected_for_this_reconciliation": False,
        },
    ]


def _performance() -> dict[str, Any]:
    blocks = [
        {"rpm": rpm, "full_coefficient_rows": full, "partial_speed_rows": partial}
        for rpm, full, partial in (
            (1000, 30, 0), (2000, 30, 0), (3000, 30, 0), (4000, 30, 0),
            (5000, 30, 0), (6000, 30, 0), (7000, 29, 1), (8000, 29, 1),
            (9000, 29, 1), (10000, 30, 0), (11000, 30, 0), (12000, 29, 1),
            (13000, 30, 0), (14000, 29, 1), (15000, 29, 1), (16000, 29, 1),
            (17000, 29, 1),
        )
    ]
    return {
        "classification": "manufacturer_computational_prediction",
        "experimental_measurement": False,
        "rho_numeric_value_in_file": None,
        "columns": [
            {"token": "V", "unit": "mph", "definition": "model speed"},
            {"token": "J", "unit": "1", "definition": "V/nD"},
            {"token": "Pe", "unit": "1", "definition": "Ct*J/Cp"},
            {"token": "Ct", "unit": "1", "definition": "T/(rho * n**2 * D**4)"},
            {"token": "Cp", "unit": "1", "definition": "P/(rho * n**3 * D**5)"},
            {"token": "PWR", "unit": "Hp", "definition": "published power"},
            {"token": "Torque", "unit": "In-Lbf", "definition": "published torque"},
            {"token": "Thrust", "unit": "Lbf", "definition": "published thrust"},
            {"token": "PWR", "unit": "W", "definition": "published power"},
            {"token": "Torque", "unit": "N-m", "definition": "published torque"},
            {"token": "Thrust", "unit": "N", "definition": "published thrust"},
            {"token": "THR/PWR", "unit": "g/W", "definition": "published thrust per power"},
            {"token": "Mach", "unit": "1", "definition": "at prop tip"},
            {"token": "Reyn", "unit": "1", "definition": "at 75% of span"},
            {"token": "FOM", "unit": "1", "definition": "figure of merit"},
        ],
        "rpm_blocks": blocks,
        "full_coefficient_row_count": sum(block["full_coefficient_rows"] for block in blocks),
        "partial_speed_row_count": sum(block["partial_speed_rows"] for block in blocks),
        "partial_speed_row_contents": "V and J tokens only; the other published fields are blank.",
        "speed_line_count": sum(
            block["full_coefficient_rows"] + block["partial_speed_rows"] for block in blocks
        ),
        "column_count": 15,
        "full_table_committed": False,
    }


def _static_row() -> dict[str, str]:
    return {
        "condition": "PROP RPM = 4000 and V = 0.00 mph",
        "source": "published PER3_13x55MR.dat tokens",
        "V_mph": "0.00",
        "J": "0.0000",
        "Pe": "0.0000",
        "Ct": "0.0941",
        "Cp": "0.0325",
        "PWR_Hp": "0.061",
        "Torque_In_Lbf": "0.959",
        "Thrust_Lbf": "1.349",
        "PWR_W": "45.403",
        "Torque_N_m": "0.108",
        "Thrust_N": "6.002",
        "THR_PWR_g_per_W": "13.479",
        "Mach": "0.21",
        "Reyn_token": "76245.",
        "FOM": "0.7095",
    }


def _gaps() -> list[dict[str, str]]:
    unread = "Not read. The named docx bytes were not in the workspace."
    return [
        {
            "quantity": "Exact 13x5.5MR identity versus E, pusher, and folding variants",
            "available_from_apc": "Distinct SKUs, hub diameters, weights, and file hashes.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "Catalog rows and the hashed PE0/PER3 headers.",
            "missing_handoff": "Confirm which SKU and rotation the CAD represents.",
        },
        {
            "quantity": "Diameter",
            "available_from_apc": "Nominal 330.2 mm, footer-based 328.676 mm, last station 328.93 mm.",
            "reported_by_ansys": "Task states 329.3519 mm. That value was not read from the docx.",
            "reproducible_from_retained_inputs": "The three APC diameters and their inequalities.",
            "missing_handoff": "CAD diameter definition, units, and the solid that produced 329.3519 mm.",
        },
        {
            "quantity": "Hub size",
            "available_from_apc": "Catalog hub diameter 0.65 in. PE0 HUBRAD 0.32 in, which is 0.64 in diameter.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "Both published APC values.",
            "missing_handoff": "Which hub surface the CAD measures.",
        },
        {
            "quantity": "Mass",
            "available_from_apc": "PE0 0.054915 lb / 0.024905 kg. Catalog 0.85 oz, 0.0529 lb, and 23.994911 g.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "The published pairs are not the same number.",
            "missing_handoff": "CAD mass and the material density actually solved.",
        },
        {
            "quantity": "4000 RPM static thrust, torque, and power",
            "available_from_apc": "Published prediction 6.002 N, 0.108 N-m, 45.403 W.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "Rounded 0.108 N-m times 4000 RPM does not reproduce 45.403 W.",
            "missing_handoff": "Engineer's independent thrust, torque, and power, with their definitions.",
        },
        {
            "quantity": "Advance condition actually solved",
            "available_from_apc": "4000 RPM has 30 speed rows from 0.00 mph through the file's last row.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "No ANSYS airspeed or advance ratio is available to select a row.",
            "missing_handoff": "Freestream speed, RPM, and reference density used in Fluent.",
        },
        {
            "quantity": "Coefficient and force definitions",
            "available_from_apc": "Ct, Cp, J, and Pe formulas. Numeric rho is absent.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "Formula text only.",
            "missing_handoff": "Force and moment definitions, component breakdown, and reference quantities.",
        },
        {
            "quantity": "Last iteration versus averaging window",
            "available_from_apc": "Not an APC performance-file quantity.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "No history was supplied.",
            "missing_handoff": "Complete convergence and load histories, with the window stated separately from the last iteration.",
        },
        {
            "quantity": "Mesh, wall resolution, and radial loads",
            "available_from_apc": "Not in the performance file.",
            "reported_by_ansys": unread,
            "reproducible_from_retained_inputs": "No mesh or radial export was supplied.",
            "missing_handoff": "Post-repair mesh statistics, wall-resolution evidence, and any existing radial-load export.",
        },
        {
            "quantity": "Section polars for the five selectable profiles",
            "available_from_apc": "PE0 names E63 and APC12 at stated stations. It does not supply those coordinates or a polar.",
            "reported_by_ansys": "Not read. The named docx bytes were not in the workspace.",
            "reproducible_from_retained_inputs": "No.",
            "missing_handoff": "Not requested from this APC/CFD package. Coordinate-bound polars remain a separate blocked study.",
        },
    ]


def _handoff() -> dict[str, list[str]]:
    return {
        "existing_files": [
            f"Provide {ANSYS_FILENAME} with SHA-256 {ANSYS_EXPECTED_SHA256}.",
            "Exact CAD of the solid that was meshed, including units and the feature that measures diameter.",
            "Fluent case and data files, or the solver archive, with the settings actually run.",
            "Complete residual and thrust/torque histories.",
            "Written force and moment definitions and the component breakdown.",
            "Post-repair mesh statistics and wall-resolution evidence.",
            "Any radial-load export that already exists.",
        ],
        "proposed_future_calculations": [
            "After those files are in hand, one same-mesh second-order 4000 RPM comparison.",
            "Mesh and domain changes only as a later, separate study.",
        ],
    }


def _next_step() -> list[str]:
    return [
        "Assess the evidence now in hand: APC identities disagree with each other and with the task-supplied CAD diameter, and the ANSYS draft has not been read.",
        "Do not tune a result to the APC prediction and do not copy the APC static load into the CFD record.",
        "When the report and solver files arrive, compare the engineer's retained thrust, torque, and power with the published 4000 RPM row that matches the solved airspeed.",
        "The first proposed calculation is a same-mesh second-order rerun at 4000 RPM. It is not authorized by this inventory.",
        "Mesh and domain studies stay behind that same-mesh comparison.",
    ]


def render_apc_13x55mr_reconciliation(report: dict[str, Any]) -> str:
    """Render the reconciliation, handoff, and next step."""
    diameters = report["diameters_mm"]
    static = report["published_4000_rpm_static_row"]
    derived = report["derived_checks"]
    lines = [
        "# APC 13x5.5MR and ANSYS reconciliation",
        "",
        "This is a source inventory and gap record. It is not a CFD, BEM, or qualification result.",
        "physical_qualification: false",
        "Genuine two-profile comparison: UNESTABLISHED",
        "",
        "## What was read",
        "",
        "Official APC downloads were retrieved on 2026-10-16 and kept under the gitignored local path",
        "`outputs/apc_13x55mr_local/`. The full performance table is not committed.",
        "Geometry identity uses the existing PE0 parser. The local reporting contract is",
        "[local APC PE0 geometry reporting](../../docs/local_apc_pe0_geometry_reporting.md).",
        "Its aerodynamic blade shortcut was not called.",
        "The first-party files in `data/propellers/apc_202602/` are synthetic fixtures, not this model.",
        "",
        f"The ANSYS draft `{report['ansys_report']['filename']}` was not in the workspace.",
        f"Its expected SHA-256 `{report['ansys_report']['expected_sha256']}` was not verified.",
        "Figures, tables, last-iteration values, and averaging-window statistics were not read.",
        f"The task states a CAD diameter of {diameters['task_supplied_cad']} mm. That statement is not a file reading.",
        "",
        "## Model separation",
        "",
        "The selected file is fixed multi-rotor 13x5.5MR, SKU LP13055MR.",
        "13x5.5E is a thin-electric propeller with catalog hub diameter 0.80 in and a different PE0 hub radius.",
        "13x5.5MRP is the reverse-rotation pusher. 13x5.5MRF-L(B) and 13x5.5MRF-R(B) are folding blades whose hubs are not included.",
        "Matching the text 13x5.5 does not make those geometries the same solid.",
        "",
        "## Diameters",
        "",
        f"Nominal product diameter: 13 in = {diameters['nominal_product']} mm.",
        f"PE0 footer RADIUS 6.47 in gives diameter {diameters['pe0_footer_radius_times_two']} mm.",
        f"The last PE0 station, 6.475 in, gives {diameters['pe0_last_station_times_two']} mm and sits beyond the footer radius.",
        f"The task-supplied CAD diameter is {diameters['task_supplied_cad']} mm.",
        "These four numbers are not the same. Nothing in this record rescales one onto another.",
        "Catalog hub diameter is 0.65 in. Twice the PE0 HUBRAD of 0.32 in is 0.64 in. That difference stays unresolved.",
        "",
        "PE0 `v2025-1001`, simulation date 2026-02-24, member SHA-256",
        "`2972e1b99215f2eb052e586e48cc59730cbfd4f08c6627ea7461a8afa150c30f`,",
        "matches the existing public pin. That member is in `PE0-FILES_WEB-202602.zipx`.",
        "The performance file is a different archive, `PERFILES_WEB-202602.zipx`, and its internal",
        "header is `v2022-0915`, simulation date 2022-09-22. The shared 202602 label does not prove",
        "that the performance prediction used the 2026 stations.",
        "",
        "Published masses also differ. The PE0 weight lines, after the RADIUS/HUBRAD/HUBTRA/BLADES footer,",
        "say 0.054915 lb and 0.024905 kg.",
        "The catalog says 0.85 oz, 0.0529 lb, and 23.994911 g. Both pairs are published values.",
        "",
        "The PE0 file names E63 at 3.70 in and APC12 at 6.00 in. Those are vendor section labels,",
        "not coordinate files for the five selectable project profiles.",
        "",
        "## Performance table",
        "",
        "Classification: manufacturer computational prediction, not an experiment.",
        "File `https://www.apcprop.com/files/PER3_13x55MR.dat`, SHA-256",
        "`bcf3914a4f7ac4c843823d6b9ebf26120824f2052ed145e03a1dad8246ec9751`.",
        "That byte hash equals the 13x5.5MR member of `PERFILES_WEB-202602.zipx`.",
        "The file has 17 RPM blocks from 1000 through 17000 and 15 columns.",
        "502 lines contain a full coefficient row. Eight further lines, at 7000, 8000, 9000,",
        "12000, 14000, 15000, 16000, and 17000 RPM, contain only V and J. Their other fields are blank.",
        "That is 510 speed lines. Blank fields are not filled in.",
        "Ct and Cp are defined with rho. The file does not state a numeric density.",
        "Airfoil aero data are described as polar diagrams.",
        "",
        "The 4000 RPM, zero-speed published tokens are thrust 6.002 N, torque 0.108 N-m, and power 45.403 W,",
        f"with Ct {static['Ct']} and Cp {static['Cp']}.",
        f"Multiplying the published 0.108 N-m by {derived['omega_4000_rpm_rad_s']:.12g} rad/s gives",
        f"{derived['power_w_from_published_torque_0_108_Nm']:.6g} W, which is not the published 45.403 W.",
        "The difference is displayed-torque rounding. It is not a replacement APC result.",
        "The other speed lines stay in the local file.",
        "",
        "No ANSYS thrust, torque, or power is available, so this record does not compare them",
        "and does not copy the APC values into a CFD result.",
        "",
        "## Source and gap matrix",
        "",
    ]
    for row in report["gap_matrix"]:
        lines.extend([
            f"### {row['quantity']}",
            "",
            f"Available from APC: {row['available_from_apc']}",
            f"Reported by the ANSYS engineer: {row['reported_by_ansys']}",
            f"Reproducible from retained inputs: {row['reproducible_from_retained_inputs']}",
            f"Missing handoff: {row['missing_handoff']}",
            "",
        ])
    lines.extend([
        "## Engineer handoff",
        "",
        "Existing files:",
        "",
    ])
    lines.extend(f"- {item}" for item in report["engineer_handoff"]["existing_files"])
    lines.extend(["", "Proposed future calculations, not existing files:", ""])
    lines.extend(f"- {item}" for item in report["engineer_handoff"]["proposed_future_calculations"])
    lines.extend(["", "## Next step", ""])
    lines.extend(f"{index}. {step}" for index, step in enumerate(report["next_step"], start=1))
    lines.extend([
        "",
        "The 13-inch APC benchmark stays separate from the 250 mm jointed design and from the blocked 7100 RPM polar study.",
        "A full-rotor load does not supply coordinate-bound section polars.",
        "The APC/CFD difference, once it can be computed, does not establish joint loss, structural adequacy,",
        "vibration acceptance, or controlled folding.",
        "",
    ])
    return "\n".join(lines)
