"""Printed-pin hinge demonstrator: geometry from the regenerated solids, retention, access, fold, evidence, package."""
import json
import zipfile
from pathlib import Path

import pytest

from pyfoldable.prototype import design as pd, explore, fit, printed_pin as pp, study

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def f1s():
    return pd.with_changes(explore.candidate_design(pd.default_design(ROOT), ROOT, study.F1S_PARAMS), name="13in-F1S")


@pytest.fixture(scope="module")
def demo(f1s):
    pytest.importorskip("build123d")
    return pp.build(f1s)


@pytest.fixture(scope="module")
def chk(demo):
    return pp.check(demo)


@pytest.fixture(scope="module")
def pred(f1s):
    """Record context without CAD: identity, coupon steps and pin variants are all a record is validated against."""
    return {"kit_design_sha256": pp.demo_identity(f1s), "kit_design_name": f1s.name,
            "coupon_steps_mm": list(fit.COUPON_STEPS_MM), "pin_diameters_mm": list(pp.PIN_DIAMETERS_MM)}


def _trial(pred, f1s, **over):
    rec = json.loads(pp.template(pred, fit.declared_prefill(f1s)))
    rec.update(print_nozzle_mm=0.4, print_layer_mm=0.2, print_walls=3, print_infill_fraction=1.0,
               print_slicer="Bambu Studio 02.09", pin_print_orientation="dik, kafa tablada", pin_variant_mm=3.9,
               pin_diameter_a_mm=3.93, insertion_fit="akıcı", clip_installs=True, clip_retains=True,
               rotation_free=True, open_stop_seats=True, cycle_count=50)
    rec.update(over)
    return json.dumps(rec, ensure_ascii=False)


# ------------------------------------------------------------------------------------------------ geometry (CAD)
def test_pin_length_is_derived_from_the_regenerated_lug_stack(demo, f1s):
    (p0, _), (_, q1) = f1s.lug_bands_mm
    prox, dist = demo["parts"].proximal, demo["parts"].distal
    assert prox.bounding_box().min.Z == pytest.approx(p0, abs=1e-6)
    assert dist.bounding_box().max.Z == pytest.approx(q1, abs=1e-6)
    assert demo["stack_mm"] == pytest.approx(q1 - p0, abs=1e-6)
    s = pp.SPEC
    length = s.head_height_mm + demo["stack_mm"] + s.stack_allowance_mm + s.clip_thickness_mm + s.groove_slack_mm + s.end_mm
    assert set(demo["pins"]) == set(pp.PIN_DIAMETERS_MM)
    for dia, pin in demo["pins"].items():
        bb = pin.bounding_box()
        assert pin.is_valid() and len(pin.solids()) == 1
        assert bb.min.Z == pytest.approx(0.0, abs=1e-6) and bb.max.Z == pytest.approx(length, abs=1e-6)
        assert bb.size.X == pytest.approx(s.head_diameter_mm, abs=1e-3)
    clip = demo["clip"]
    assert clip.is_valid() and len(clip.solids()) == 1
    assert clip.bounding_box().size.Z == pytest.approx(s.clip_thickness_mm, abs=1e-6)


def test_retention_is_consistent_and_its_reduced_section_is_outside_the_bearing_span(chk):
    g = chk["geometry"]
    assert g["groove_start_above_stack_mm"] > 0.0
    assert g["clip_mouth_mm"] < g["groove_root_mm"] < g["clip_seat_mm"] < min(pp.PIN_DIAMETERS_MM)
    assert g["float_nominal_mm"] == pytest.approx(pp.SPEC.stack_allowance_mm + pp.SPEC.groove_slack_mm)
    assert 0.1 <= g["float_nominal_mm"] <= 0.4
    assert g["assembles_up_to_extra_stack_mm"] == pytest.approx(g["float_nominal_mm"])
    assert g["head_diameter_mm"] <= g["spot_face_diameter_mm"]


def test_no_part_interferes_and_pin_and_clip_have_free_access(chk):
    assert chk["interference_mm3"] and all(v < 1e-3 for v in chk["interference_mm3"].values()), chk["interference_mm3"]
    assert chk["access"]["pin_path_clear"] and chk["access"]["clip_path_clear"]


def test_fold_check_reports_open_tightest_and_folded_configurations(chk):
    cf, fold = chk["configurations"], chk["fold"]
    assert cf["open"] == 0.0 and cf["folded"] <= cf["tightest"] < 0.0
    assert fold["useful_travel_deg"] == pytest.approx(-cf["folded"])
    assert fold["min_gap_mm"] >= 0.0                      # no body contact inside the useful travel
    assert fold["useful_travel_deg"] >= fold["metal_design_required_travel_deg"]       # 143° here: nose stop at 144°


# ------------------------------------------------------------------------------------------ record and evidence
def test_template_prefills_only_the_confirmed_setup(pred, f1s):
    rec = json.loads(pp.template(pred, fit.declared_prefill(f1s)))
    assert rec["schema"] == pp.SCHEMA and rec["kit_design_sha256"] == pred["kit_design_sha256"]
    assert rec["print_printer"] == "Bambu Lab P1S" and rec["print_material_family"] == "PLA"
    assert all(rec[k] is None for k in ("print_nozzle_mm", "pin_variant_mm", "pin_diameter_a_mm", "cycle_count",
                                        "rotation_free", "insertion_fit"))


def test_printed_pin_observations_are_never_direct_evidence_for_the_metal_assembly(pred, f1s):
    out = pp.classify(pp.parse(_trial(pred, f1s), pred), pred, f1s)
    assert out["evidence"] == "printed_pin_observation" and out["direct_for_metal"] is False
    assert "design" not in out                                  # nothing to apply to the metal-pin design
    assert any("metal" in r for r in out["reasons"]) and any("geometrik" in r for r in out["reasons"])


def test_metal_and_printed_pin_records_cannot_be_swapped(pred, f1s):
    with pytest.raises(fit.RecordError):
        fit.parse(_trial(pred, f1s), {**pred, "fit_pair_clearances_mm": [0.2]})
    with pytest.raises(fit.RecordError, match="schema"):
        pp.parse(_trial(pred, f1s, schema=fit.SCHEMA), pred)


def test_unmeasured_fields_stay_empty_and_required_observations_are_enforced(pred, f1s):
    assert pp.parse(_trial(pred, f1s, pin_diameter_b_mm=None, folded_stop_deg=None), pred)["folded_stop_deg"] is None
    with pytest.raises(fit.RecordError, match="cycle_count"):
        pp.parse(_trial(pred, f1s, cycle_count=None), pred)
    with pytest.raises(fit.RecordError, match="pin_variant_mm"):
        pp.parse(_trial(pred, f1s, pin_variant_mm=3.85), pred)


def test_a_changed_process_is_listed_and_problems_are_warned(pred, f1s):
    out = pp.classify(pp.parse(_trial(pred, f1s, print_material_family="ASA", clip_retains=False,
                                      interference_observed="burun pede sürtüyor"), pred), pred, f1s)
    assert any("ASA" in r for r in out["process_differences"])
    assert any("klips" in w for w in out["warnings"]) and any("temas" in w for w in out["warnings"])


# ------------------------------------------------------------------------------------------------------ package
def test_package_is_self_contained_print_oriented_and_carries_no_operating_limit(f1s, demo, chk, tmp_path):
    import xml.etree.ElementTree as ET
    out = pp.export_package(f1s, tmp_path, demo=demo, chk=chk)
    names = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    first = {"3mf/01A_kucuk_parcalar.3mf", "3mf/01B_mafsal_cifti.3mf"}
    assert first <= names and {n for n in names if n.startswith("3mf/")} == first
    assert {"00_ONCE_BENI_OKU.md", "BASKI_REHBERI.md", "MONTAJ.md", "DENEME_PROTOKOLU.md", "BASKI_VE_DENEME_KAYDI.md",
            "deneme_kaydi.json", "predictions.json", "design.json", "SHA256SUMS",
            "gorseller/patlatilmis_montaj.png", "gorseller/pim_kesiti.png", "gorseller/katlanma_konumlari.png"} <= names
    assert any(n.startswith("step/") for n in names) and any(n.startswith("stl/") for n in names)
    docs = {n: (tmp_path / n).read_text(encoding="utf-8") for n in names if n.endswith(".md")}
    assert not any("README" in t for t in docs.values())
    start = docs["00_ONCE_BENI_OKU.md"]
    assert all(f in start for f in first) and "metal" in start.lower() and "fit_kit_F1S" not in start
    p = out["predictions"]
    assert p["operating_envelope"] is None and p["rpm_limit"] is None and p["physical_qualification"] is False
    assert p["evidence"] == "printed_pin_observation" and p["kit_design_sha256"] == pp.demo_identity(f1s)
    assert p["hole_diameter_mm"] == pytest.approx(f1s.hole_diameter_mm)         # metal design hole, not resized
    rec = json.loads((tmp_path / "deneme_kaydi.json").read_text(encoding="utf-8"))
    assert rec["schema"] == pp.SCHEMA and rec["kit_design_sha256"] == p["kit_design_sha256"]
    assert rec["cycle_count"] is None and rec["print_printer"] == "Bambu Lab P1S"
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    with zipfile.ZipFile(tmp_path / "3mf/01A_kucuk_parcalar.3mf") as z:
        root = ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith(".model"))))
    named = sorted(o.get("name") for o in root.findall(".//m:object", ns) if o.get("name"))
    assert sum(n.startswith("F1S_pim_D") for n in named) == len(pp.PIN_DIAMETERS_MM)
    assert sum(n.startswith("F1S_klips") for n in named) >= 1 and any(n.startswith("F1S_kupon") for n in named)
    zs = [float(v.get("z")) for v in root.iter("{%s}vertex" % ns["m"])]
    assert min(zs) == pytest.approx(0.0, abs=1e-3)                              # everything on the bed
    sums = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8")
    assert "3mf/01A_kucuk_parcalar.3mf" in sums and "deneme_kaydi.json" in sums


def test_fold_travel_ends_before_contact_and_refuses_contact_at_the_first_step():
    sw = {"angles_deg": [-2.0, -3.0, -4.0, -5.0], "gap_mm": [1.0, 0.5, 0.2, -0.1],
          "nose_gap_mm": [float("inf")] * 4}
    travel, k = pp.fold_travel(sw)
    assert travel == 4.0 and k == 2                       # one step before body contact; tightest inside the travel
    with pytest.raises(RuntimeError, match="kontak|temas"):
        pp.fold_travel({**sw, "gap_mm": [-0.1, 0.5, 0.2, 0.1]})


def test_committed_package_matches_the_code_and_states_the_angle_convention(f1s):
    import hashlib
    base = ROOT / "reports/prototype_13in_20261118/F1S_printed_pin_demo"
    for line in (base / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        h, name = line.split("  ", 1)
        assert hashlib.sha256((base / name).read_bytes()).hexdigest() == h, name
    p = json.loads((base / "predictions.json").read_text(encoding="utf-8"))
    assert p["kit_design_sha256"] == pp.demo_identity(f1s) and p["design_sha256"] == f1s.identity
    proto = (base / "DENEME_PROTOKOLU.md").read_text(encoding="utf-8")
    assert f"{p['fold']['useful_travel_deg']:.0f}°" in proto and "negatif" in proto
    assert "negatif" in (base / "MONTAJ.md").read_text(encoding="utf-8")
