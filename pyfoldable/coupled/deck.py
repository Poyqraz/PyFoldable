"""Generate DUST, MBDyn and preCICE input decks (pure text functions).

Every file is a deterministic function of the :class:`CoupledCase` and the C81
text, so restoration can regenerate and compare decks without any solver.
Syntax follows the pinned sources:

* DUST 3b1d2e61: parametric lifting-line component (src/io/mod_ll_io.f90),
  rigid coupling (src/geo/mod_build_geo.f90, src/precice/mod_precice.f90),
  options of src/general/mod_sim_param.f90;
* MBDyn develop 55c86cc6: manual/input/elements.tex (axial rotation, total
  joint, revolute hinge, deformable hinge, driven, external structural),
  manual/input/general.tex (double linear viscoelastic);
* preCICE 2.5.0 XML schema as used by DUST's coupled examples.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import MODEL_ID, SCHEMA_VERSION
from .frames import blade_frame, fmt_matrix_rowwise, matmul, matvec, rot_z
from .model import CoupledCase, SegmentSection

NODE_Z_OFFSET_M = 0.01  # distinct preCICE vertex labels per blade, along the hinge-axis direction
GROUND, HUB = 1, 2
PROX, DIST = 100, 200
J_CLAMP, J_DRIVE, J_RIGID, J_HINGE, J_SPRING, J_LATCH = 1, 2, 300, 400, 500, 600
F_AERO = 700


def _r(x: float) -> str:
    return repr(float(x))


def _vec(v) -> str:
    return ", ".join(_r(c) for c in v)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def coupling_nodes(case: CoupledCase) -> list[dict]:
    """Ordered coupling nodes: for each blade, proximal then distal."""
    g = case.geometry
    nodes = []
    for b in range(g.blade_count):
        z = NODE_Z_OFFSET_M * b
        rb = blade_frame(b, g.blade_count)
        for kind, label, r_node in (("proximal", PROX + b, g.root_radius_m), ("distal", DIST + b, g.hinge_radius_m)):
            local = (0.0, r_node, z)
            nodes.append({"blade": b, "segment": kind, "mbdyn_label": label, "dust_component": f"blade{b + 1}_{kind}",
                          "local": local, "global": matvec(rb, local)})
    return nodes


def _allocate_elements(sections: tuple[SegmentSection, ...], total: int) -> list[int]:
    spans = [b.radius_m - a.radius_m for a, b in zip(sections, sections[1:])]
    n = len(spans)
    total = max(total, n)
    base = [1] * n
    rest = total - n
    ideal = [rest * s / sum(spans) for s in spans]
    extra = [int(math.floor(v)) for v in ideal]
    left = rest - sum(extra)
    order = sorted(range(n), key=lambda i: ideal[i] - extra[i], reverse=True)
    for i in order[:left]:
        extra[i] += 1
    return [a + e for a, e in zip(base, extra)]


def dust_component(case: CoupledCase, node: dict, sections, *, coupled: bool, airfoil_file: str) -> str:
    counts = _allocate_elements(sections, case.controls.elements_per_segment)
    lines = ["! PyFoldable generated lifting-line segment (quarter-chord line, body frame:",
             "! x chord LE->TE, y span, z lift normal; twist about the quarter-chord line)",
             "mesh_file_type = parametric", "el_type = l"]
    if coupled:
        lines += ["coupled = T", "coupling_type = rigid",
                  f"coupling_node = (/ {_vec(node['local'])} /)",
                  "coupling_node_orientation = (/ 1.0,0.0,0.0, 0.0,1.0,0.0, 0.0,0.0,1.0 /)"]
    lines += [f"starting_point = (/ 0.0, {_r(sections[0].radius_m)}, 0.0 /)",
              "reference_chord_fraction = 0.0", "twist_linear_interpolation = T", ""]
    for i, s in enumerate(sections):
        lines += [f"chord = {_r(s.chord_m)}", f"twist = {_r(math.degrees(s.twist_rad))}",
                  f"airfoil_table = {airfoil_file}", ""]
        if i < len(sections) - 1:
            lines += [f"span = {_r(sections[i + 1].radius_m - s.radius_m)}", "sweep = 0.0", "dihed = 0.0",
                      f"nelem_span = {counts[i]}", "type_span = uniform", ""]
    return "\n".join(lines) + "\n"


def dust_references(case: CoupledCase, *, coupled: bool) -> str:
    g = case.geometry
    out = []
    if not coupled:
        out += ["reference_tag = Rotor", "parent_tag = 0", "origin = (/0.0, 0.0, 0.0/)",
                "orientation = (/1.0,0.0,0.0, 0.0,1.0,0.0, 0.0,0.0,1.0/)", "multiple = F", "moving = T",
                "motion = {", " pole = {", "  input = position", "  input_type = simple_function",
                "  function = (/ 0, 0, 0 /)", "  amplitude = 0.0", "  vector = (/ 0.0, 0.0, 0.0 /)",
                "  omega = (/ 0.0, 0.0, 0.0 /)", "  phase = (/ 0.0, 0.0, 0.0 /)", "  offset = (/ 0.0, 0.0, 0.0 /)", " }",
                " rotation = {", "  input = velocity", "  input_type = simple_function", "  function = 0",
                "  Axis = (/ 0.0, 0.0, 1.0 /)", f"  amplitude = {_r(case.omega_rad_s)}", "  omega = 0.0",
                "  phase = 0.0", "  offset = 0.0", "  psi_0 = 0.0", " }", "}", ""]
    parent = "0" if coupled else "Rotor"
    for b in range(g.blade_count):
        rb = blade_frame(b, g.blade_count)
        # DUST orientation lists the local unit vectors (columns of rb)
        cols = [rb[i][j] for j in range(3) for i in range(3)]
        out += [f"reference_tag = Blade{b + 1}", f"parent_tag = {parent}", "origin = (/0.0, 0.0, 0.0/)",
                f"orientation = (/ {_vec(cols)} /)", "multiple = F", "moving = F", ""]
    return "\n".join(out)


def dust_pre(case: CoupledCase) -> str:
    lines = []
    for node in coupling_nodes(case):
        lines += [f"comp_name = {node['dust_component']}",
                  f"geo_file = ./comps/{node['dust_component']}.in",
                  f"ref_tag = Blade{node['blade'] + 1}", ""]
    lines += ["file_name = geo_input.h5"]
    return "\n".join(lines) + "\n"


def dust_main(case: CoupledCase, *, coupled: bool) -> str:
    g, c = case.geometry, case.controls
    box_r = c.wake_box_radial_factor * g.tip_radius_m
    lines = ["! PyFoldable generated DUST run", "basename = ./Output/run", "",
             "tstart = 0.0", f"tend = {_r(case.final_time_s)}", f"dt = {_r(case.dt_s)}", f"dt_out = {_r(case.dt_s)}",
             "output_start = T", "debug_level = 3", "",
             f"u_inf = (/ 0.0, 0.0, {_r(-case.inflow_m_s)} /)",
             f"u_ref = {_r(case.omega_rad_s * g.tip_radius_m)}",
             f"rho_inf = {_r(case.density_kg_m3)}", f"a_inf = {_r(case.speed_of_sound_m_s)}",
             f"mu_inf = {_r(case.viscosity_pa_s)}", "",
             "geometry_file = geo_input.h5", "reference_file = References.in", "",
             f"n_wake_panels = {c.n_wake_panels}", f"n_wake_particles = {c.max_wake_particles}",
             f"particles_box_min = (/ {_r(-box_r)}, {_r(-box_r)}, {_r(-c.wake_box_axial_m)} /)",
             f"particles_box_max = (/ {_r(box_r)}, {_r(box_r)}, {_r(0.5 * g.tip_radius_m)} /)",
             "k_vortex_rad = 1.0", f"vortstretch = {'T' if c.vortex_stretching else 'F'}", "diffusion = T",
             "penetration_avoidance = F", ""]
    if c.fmm:
        side = 2 * box_r
        lines += ["fmm = T", f"box_length = {_r(side)}",
                  f"n_box = (/ 1, 1, {max(1, int(math.ceil((c.wake_box_axial_m + 0.5 * g.tip_radius_m) / side)))} /)",
                  f"octree_origin = (/ {_r(-box_r)}, {_r(-box_r)}, {_r(-c.wake_box_axial_m)} /)",
                  "n_octree_levels = 6", "min_octree_part = 5", "multipole_degree = 2", ""]
    else:
        lines += ["fmm = F", ""]
    lines += ["ll_solver = GammaMethod", f"ll_tol = {_r(c.ll_tol)}", f"ll_max_iter = {c.ll_max_iter}",
              f"ll_damp = {_r(c.ll_damp)}", "ll_stall_regularisation = F", "ll_reynolds_corrections = F",
              "ll_loads_avl = F"]
    if coupled:
        lines += ["", "precice_config = ../precice-config.xml"]
    return "\n".join(lines) + "\n"


def mbdyn_model(case: CoupledCase, *, aero: bool = True) -> str:
    """``aero=False`` omits the external force (mechanical verification decks only)."""
    g, m, c = case.geometry, case.mechanics, case.controls
    n = g.blade_count
    w = case.omega_rad_s
    latch = m.release_time_s > 0.0
    joints = 2 + 3 * n + (n if latch else 0)
    L = ["# PyFoldable generated MBDyn model: prescribed shaft speed, rigid proximal/distal segments,",
         "# ideal in-plane fold hinge (axis parallel to shaft), spring/damper/unilateral stop law.",
         "begin: data;", "  problem: initial value;", "end: data;", "",
         "begin: initial value;", "  initial time: 0.;", f"  final time: {_r(case.final_time_s)};",
         f"  time step: {_r(case.dt_s)};", f"  max iterations: {c.mbdyn_max_iterations};",
         f"  tolerance: {_r(c.mbdyn_tolerance)};", "  derivatives tolerance: 1e-6;",
         "  derivatives max iterations: 100;",
         "  derivatives coefficient: 1e-3, auto, max iterations, 100, factor, 3.0;",
         "  linear solver: naive, colamd, pivot factor, 1e-5;",
         # ms with asymptotic radius rho (default 0.6). A rigidly spinning rotor with rho = 0 shows an
         # O(dt^3) spurious drive/hinge torque (mechanical artifact study); rho = 0.6 keeps it below
         # 3e-3 N m at 5 deg azimuth steps. Constraint reactions show a decaying start/release transient.
         f"  method: ms, {_r(c.mbdyn_spectral_radius)}, {_r(c.mbdyn_spectral_radius)};",
         "  output: iterations;", "end: initial value;", "",
         "begin: control data;", f"  structural nodes: {2 + 2 * n};", f"  rigid bodies: {1 + 2 * n};",
         f"  joints: {joints};", *(["  forces: 1;"] if aero else []), "  default orientation: orientation vector;",
         "  default output: all;", "end: control data;", "",
         "begin: nodes;",
         f"  structural: {GROUND}, static, null, eye, null, null;",
         f"  structural: {HUB}, dynamic, null, eye, null, 0., 0., {_r(w)};"]
    hinge_pts = {}
    for node in coupling_nodes(case):
        b = node["blade"]
        rb = blade_frame(b, n)
        pos = node["global"]
        vel = (-w * pos[1], w * pos[0], 0.0)
        if node["segment"] == "proximal":
            rot, wz = rb, w
        else:
            rot, wz = matmul(rot_z(m.initial_fold_rad), rb), w + m.initial_rate_rad_s
            hinge_pts[b] = pos
        L.append(f"  structural: {node['mbdyn_label']}, dynamic, {_vec(pos)}, matr, {fmt_matrix_rowwise(rot)}, "
                 f"{_vec(vel)}, 0., 0., {_r(wz)};")
    L += ["end: nodes;", "", "begin: elements;",
          f"  body: {HUB}, {HUB}, {_r(m.hub_mass_kg)}, null, diag, 1e-4, 1e-4, 1e-4;"]
    seg_mid = 0.5 * (g.root_radius_m + g.hinge_radius_m)
    prox_len = g.hinge_radius_m - g.root_radius_m
    jp = m.proximal_mass_kg * prox_len ** 2 / 12.0 + 1e-8
    for b in range(n):
        z = NODE_Z_OFFSET_M * b
        L.append(f"  body: {PROX + b}, {PROX + b}, {_r(m.proximal_mass_kg)}, 0., {_r(seg_mid - g.root_radius_m)}, {_r(-z)}, "
                 f"diag, {_r(jp)}, {_r(jp)}, {_r(jp)};")
        jd = m.distal_inertia_cg_kg_m2
        L.append(f"  body: {DIST + b}, {DIST + b}, {_r(m.distal_mass_kg)}, 0., {_r(m.distal_cg_from_hinge_m)}, {_r(-z)}, "
                 f"diag, {_r(jd)}, {_r(jd)}, {_r(jd)};")
    L += ["", f"  joint: {J_CLAMP}, clamp, {GROUND}, node, node;",
          f"  joint: {J_DRIVE}, axial rotation, {GROUND}, null, {HUB}, null, const, {_r(w)};"]
    for b in range(n):
        rb = blade_frame(b, n)
        prox_pos = matvec(rb, (0.0, g.root_radius_m, NODE_Z_OFFSET_M * b))
        hinge = hinge_pts[b]
        R = fmt_matrix_rowwise(rb)
        L += [f"  joint: {J_RIGID + b}, total joint,",
              f"    {HUB}, position, reference, global, {_vec(prox_pos)},",
              "      position orientation, reference, global, eye, rotation orientation, reference, global, eye,",
              f"    {PROX + b}, position, reference, node, null,",
              "      position orientation, reference, global, eye, rotation orientation, reference, global, eye,",
              "    position constraint, active, active, active, null,",
              "    orientation constraint, active, active, active, null;",
              f"  joint: {J_HINGE + b}, revolute hinge,",
              f"    {PROX + b}, position, reference, global, {_vec(hinge)}, orientation, reference, global, matr, {R},",
              f"    {DIST + b}, position, reference, node, null, orientation, reference, node, eye;",
              f"  joint: {J_SPRING + b}, deformable hinge,",
              f"    {PROX + b}, position, reference, global, {_vec(hinge)}, orientation, reference, global, matr, {R},",
              f"    {DIST + b}, position, reference, node, null, orientation, reference, node, eye,",
              # strain_3 = fold angle theta; band [fold_limit, stop] uses the spring; outside, contact
              "    double linear viscoelastic,",
              f"      {_r(m.spring_nm_per_rad)}, {_r(m.stop_angle_rad)}, {_r(m.fold_limit_rad)},",
              f"      {_r(m.spring_nm_per_rad + m.stop_stiffness_nm_per_rad)}, {_r(m.hinge_damping_nm_s_per_rad)},",
              f"      second damping, {_r(m.hinge_damping_nm_s_per_rad + m.stop_damping_nm_s_per_rad)},",
              f"      prestress, 0., 0., {_r(-m.spring_nm_per_rad * m.spring_rest_rad)};"]
        if latch:
            L += [f"  driven: {J_LATCH + b}, string, \"Time < {_r(m.release_time_s)}\",",
                  f"  joint: {J_LATCH + b}, total joint,",
                  f"    {PROX + b}, position, reference, global, {_vec(hinge)},",
                  f"      position orientation, reference, global, eye, rotation orientation, reference, global, matr, {R},",
                  f"    {DIST + b}, position, reference, node, null,",
                  "      position orientation, reference, global, eye, rotation orientation, reference, node, eye,",
                  "    position constraint, inactive, inactive, inactive, null,",
                  f"    orientation constraint, inactive, inactive, active, component, 0., 0., {_r(m.initial_fold_rad)};"]
    labels = ", ".join(str(nd["mbdyn_label"]) for nd in coupling_nodes(case))
    if aero:
        L += ["", f"  force: {F_AERO}, external structural,",
              "    socket, create, yes, path, \"$MBSOCK\", no signal,",
              "    coupling, tight,", "    sorted, yes,", "    orientation, orientation vector,",
              "    accelerations, yes,", f"    {2 * n}, {labels};"]
    L += ["end: elements;", ""]
    return "\n".join(L)


def precice_config(case: CoupledCase) -> str:
    c = case.controls
    data = ("Position", "Rotation", "Velocity", "AngularVelocity", "Force", "Moment")
    use = "\n".join(f'      <use-data name="{d}" />' for d in data)
    return f"""<?xml version="1.0"?>
<!-- PyFoldable generated; structure follows DUST's coupled examples (preCICE 2.5.0). -->
<precice-configuration>
  <log>
    <sink filter="%Severity% > warning" format="%TimeStamp% %Severity% %Module%: %Message%" enabled="true" />
  </log>
  <solver-interface dimensions="3">
{chr(10).join(f'    <data:vector name="{d}" />' for d in data)}
    <mesh name="MBDynNodes">
{use}
    </mesh>
    <mesh name="dust_mesh">
{use}
    </mesh>
    <participant name="MBDyn">
      <use-mesh name="MBDynNodes" provide="yes" />
      <write-data name="Position" mesh="MBDynNodes" />
      <write-data name="Rotation" mesh="MBDynNodes" />
      <write-data name="Velocity" mesh="MBDynNodes" />
      <write-data name="AngularVelocity" mesh="MBDynNodes" />
      <read-data name="Force" mesh="MBDynNodes" />
      <read-data name="Moment" mesh="MBDynNodes" />
    </participant>
    <participant name="dust">
      <use-mesh name="dust_mesh" provide="yes" />
      <use-mesh name="MBDynNodes" from="MBDyn" />
      <write-data name="Force" mesh="dust_mesh" />
      <write-data name="Moment" mesh="dust_mesh" />
      <read-data name="Position" mesh="dust_mesh" />
      <read-data name="Rotation" mesh="dust_mesh" />
      <read-data name="Velocity" mesh="dust_mesh" />
      <read-data name="AngularVelocity" mesh="dust_mesh" />
      <mapping:nearest-neighbor direction="read" from="MBDynNodes" to="dust_mesh" constraint="consistent" />
      <mapping:nearest-neighbor direction="write" from="dust_mesh" to="MBDynNodes" constraint="conservative" />
    </participant>
    <m2n:sockets exchange-directory="./../" from="MBDyn" to="dust" />
    <coupling-scheme:serial-implicit>
      <participants first="MBDyn" second="dust" />
      <max-time value="{_r(case.final_time_s)}" />
      <time-window-size value="-1" valid-digits="10" method="first-participant" />
      <exchange data="Position" from="MBDyn" mesh="MBDynNodes" to="dust" />
      <exchange data="Rotation" from="MBDyn" mesh="MBDynNodes" to="dust" />
      <exchange data="Velocity" from="MBDyn" mesh="MBDynNodes" to="dust" />
      <exchange data="AngularVelocity" from="MBDyn" mesh="MBDynNodes" to="dust" />
      <exchange data="Force" from="dust" mesh="MBDynNodes" to="MBDyn" />
      <exchange data="Moment" from="dust" mesh="MBDynNodes" to="MBDyn" />
      <max-iterations value="{c.coupling_max_iterations}" />
      <absolute-convergence-measure limit="{_r(c.coupling_position_tol_m)}" data="Position" mesh="MBDynNodes" />
      <absolute-convergence-measure limit="{_r(c.coupling_rotation_tol_rad)}" data="Rotation" mesh="MBDynNodes" />
      <absolute-convergence-measure limit="{_r(c.coupling_velocity_tol_m_s)}" data="Velocity" mesh="MBDynNodes" />
      <absolute-convergence-measure limit="{_r(c.coupling_angular_velocity_tol_rad_s)}" data="AngularVelocity" mesh="MBDynNodes" />
      <!-- No load-based measure: with prescribed (latched) kinematics two iterates can return identical loads and
           Aitken's relaxation factor becomes 0/0 (observed NaN). The load residual is audited after the run. -->
      <acceleration:aitken>
        <data name="Force" mesh="MBDynNodes" />
        <data name="Moment" mesh="MBDynNodes" />
        <initial-relaxation value="{_r(c.aitken_initial_relaxation)}" />
      </acceleration:aitken>
    </coupling-scheme:serial-implicit>
  </solver-interface>
</precice-configuration>
"""


def adapter_config(case: CoupledCase) -> dict:
    nodes = coupling_nodes(case)
    return {"schema_version": 1, "participant": "MBDyn", "mesh": "MBDynNodes",
            "precice_config": "../precice-config.xml", "nnodes": len(nodes),
            "vertices": [list(nd["local"]) for nd in nodes],
            "mbdyn_labels": [nd["mbdyn_label"] for nd in nodes],
            "dt": case.dt_s, "n_windows": case.n_steps, "window_log": "adapter_windows.jsonl",
            "connect_timeout_s": 120}


def generate_deck(case: CoupledCase, c81_text: str, *, coupled: bool = True) -> dict[str, str]:
    """All input files (relative path -> text). No machine-specific paths."""
    profile = case.geometry.profile
    airfoil = f"./airfoil/{profile}.c81"
    files = {f"dust/airfoil/{profile}.c81": c81_text,
             "dust/dust_pre.in": dust_pre(case),
             "dust/dust.in": dust_main(case, coupled=coupled),
             "dust/References.in": dust_references(case, coupled=coupled)}
    for node in coupling_nodes(case):
        g = case.geometry
        sections = g.proximal_sections if node["segment"] == "proximal" else g.distal_sections
        files[f"dust/comps/{node['dust_component']}.in"] = dust_component(case, node, sections, coupled=coupled, airfoil_file=airfoil)
    if coupled:
        files["structure/rotor.mbd"] = mbdyn_model(case)
        files["structure/adapter_config.json"] = json.dumps(adapter_config(case), indent=2, sort_keys=True) + "\n"
        files["precice-config.xml"] = precice_config(case)
    return files


def deck_manifest(files: dict[str, str]) -> dict:
    return {"files": {k: {"sha256": _sha(v), "bytes": len(v.encode())} for k, v in sorted(files.items())},
            "deck_sha256": _sha(json.dumps({k: _sha(v) for k, v in sorted(files.items())}, sort_keys=True))}


def write_deck(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def run_definition(case: CoupledCase, deck: dict, extra: dict) -> dict:
    return {"schema_version": SCHEMA_VERSION, "artifact_class": "pyfoldable_coupled_run_definition",
            "model_id": MODEL_ID, "case": case.as_dict(), "coupling_nodes": coupling_nodes(case),
            "deck": deck_manifest(deck), **extra}
