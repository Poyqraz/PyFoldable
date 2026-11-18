"""Measurement prototype and model update: hole coupon + short joint-fit pair of one candidate, printed and measured.

Sequence (``README.md`` written by ``export_kit``): print the hole coupon, pick the smallest step that gives a running
fit with the real pin, print the fit pair with that CAD clearance (three variants are exported), then measure pin
fit, axial float, tilt under a reversing load at the load tab, break-away friction torque, open-stop seating, the
folded-stop angle and the part masses, and fill the record template. ``parse`` validates the record against the kit
it belongs to (fail closed: unknown keys, missing or out-of-range values and a different kit are refused) and
``apply`` carries the measured play and clearance into a design record (the play then replaces the worst-case model
play in the clearance check) and lists measured against model values.

Measured play is defined by two readings with the proximal clamped and the rotor plane level: the axial float a of
the distal lug at the boss, and the total vertical free movement Δ of the load-tab hole at lever L under ± load.
Tilt φ = max(0, Δ − a) / (2 L). Friction: break-away force F at the hole perpendicular to the lever, T = F L.
The self-deploy speed is where the centrifugal stop moment Ω² K equals T (no load-dependent pin friction).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .design import PrototypeDesign, to_json, with_changes

SCHEMA = "pyfoldable.prototype.fit_record/1"
MAX_BYTES = 64_000
FITS = ("girmez", "sıkı", "akıcı", "boşluklu")          # no entry / turns only with force / running / visible wobble
COUPON_STEPS_MM = (0.0, 0.1, 0.2, 0.3, 0.4)
FIT_PAIR_CLEARANCES_MM = (0.1, 0.2, 0.3)

# key: (kind, (lo, hi) or None, required, meaning)
FIELDS = {
    "schema": ("text", None, True, "kayıt şeması"),
    "kit_design_sha256": ("text", None, True, "ölçüm kitinin tasarım kimliği (predictions.json)"),
    "print_printer": ("text", None, True, "yazıcı modeli"),
    "print_material": ("text", None, True, "malzeme ve marka/seri"),
    "print_nozzle_mm": ("num", (0.1, 1.2), True, "nozul çapı [mm]"),
    "print_layer_mm": ("num", (0.04, 0.6), True, "katman yüksekliği [mm]"),
    "print_walls": ("int", (1, 20), True, "çevre duvarı sayısı"),
    "print_infill_fraction": ("num", (0.05, 1.0), True, "doluluk oranı (0–1)"),
    "pin_measured_diameter_mm": ("num", (1.0, 10.0), True, "pimin ölçülen çapı [mm]"),
    "coupon_fit": ("fits", None, True, "kupon deliği başına geçme: " + " / ".join(FITS)),
    "coupon_hole_mm": ("holes", None, False, "kupon deliği başına ölçülen çap [mm] (pim mastarı; bilinmiyorsa null)"),
    "fit_pair_clearance_mm": ("choice", None, True, "basılan uyum çiftinin CAD delik boşluğu [mm]"),
    "lug_thickness_proximal_mm": ("num", (0.5, 30.0), True, "proksimal lug ölçülen kalınlığı [mm]"),
    "lug_thickness_distal_mm": ("num", (0.5, 30.0), True, "distal lug ölçülen kalınlığı [mm]"),
    "axial_float_mm": ("num", (0.0, 3.0), True, "distal lugun pim boyunca serbest hareketi a [mm]"),
    "tilt_load_n": ("num", (0.1, 50.0), True, "eğilme ölçümündeki ± yük [N]"),
    "tilt_range_at_tab_mm": ("num", (0.0, 20.0), True, "yük deliğinde toplam düşey serbest hareket Δ [mm]"),
    "friction_breakaway_n": ("num", (0.0, 100.0), True, "katlanmayı başlatan kuvvet, delikte kola dik [N]"),
    "stop_gap_mm": ("num", (0.0, 5.0), True, "distal elle açık tutulurken burun–ped aralığı [mm] (sentil)"),
    "stop_seats": ("bool", None, True, "burun pede tam yüzeyle oturuyor mu (ışık testi)"),
    "folded_stop_deg": ("num", (0.0, 180.0), False, "katlanmış stop açısı [°] (açıölçer)"),
    "mass_fit_proximal_g": ("num", (0.1, 500.0), False, "uyum çifti proksimal kütlesi [g]"),
    "mass_fit_distal_g": ("num", (0.1, 500.0), False, "uyum çifti distal kütlesi [g]"),
    "notes": ("text", None, False, "serbest not"),
}


class RecordError(ValueError):
    """The fit record cannot be used (nothing is applied)."""


def predictions(d: PrototypeDesign, lever_mm: float, fit_masses_g, folded_stop_deg=None,
                clearances=FIT_PAIR_CLEARANCES_MM) -> dict:
    """Model values of the kit the record is compared with (the kit design's identity binds record and geometry)."""
    from .checks import joint_play
    c = d.connection
    return {
        "kit_design_sha256": d.identity, "kit_design_name": d.name, "coupon_steps_mm": list(COUPON_STEPS_MM),
        "fit_pair_clearances_mm": [float(x) for x in clearances], "lever_mm": float(lever_mm),
        "fit_masses_g": [float(m) for m in fit_masses_g], "folded_stop_deg": folded_stop_deg,
        "pin_diameter_mm": c.pin_diameter_mm, "lug_thicknesses_mm": list(d.lug_thicknesses_mm),
        "lug_gap_mm": c.lug_gap_mm, "boss_radius_mm": c.boss_radius_mm, "model_play": joint_play(d),
        "print_model": {"material": d.print_model.material, "wall_mm": d.print_model.wall_mm,
                        "infill_fraction": d.print_model.infill_fraction, "layer_mm": d.print_model.layer_mm},
    }


def template(pred: dict) -> str:
    rec = {k: None for k in FIELDS}
    rec.update(schema=SCHEMA, kit_design_sha256=pred["kit_design_sha256"], notes="",
               coupon_fit=[None] * len(pred["coupon_steps_mm"]), coupon_hole_mm=[None] * len(pred["coupon_steps_mm"]))
    return json.dumps(rec, indent=1, ensure_ascii=False)


def _number(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return abs(v) < 1e9 if isinstance(v, int) else math.isfinite(v)      # huge ints overflow math.isfinite


def parse(text: str, pred: dict) -> dict:
    """Validated record (a dict) or ``RecordError`` naming every problem."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise RecordError(f"Kayıt {MAX_BYTES} bayttan büyük.")
    try:
        raw = json.loads(text)
    except (ValueError, RecursionError) as exc:                      # JSONDecodeError, int-digit limit, nesting
        raise RecordError(f"Kayıt JSON değil: {type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise RecordError("Kayıt bir JSON nesnesi olmalı.")
    errs = [f"bilinmeyen alan: {k}" for k in raw if k not in FIELDS]
    n = len(pred["coupon_steps_mm"])
    for key, (kind, rng, required, _) in FIELDS.items():
        v = raw.get(key)
        if v is None or (kind == "text" and isinstance(v, str) and not v.strip() and required):
            if required:
                errs.append(f"{key}: zorunlu")
            continue
        if kind == "text" and not (isinstance(v, str) and len(v) <= 2000):
            errs.append(f"{key}: metin olmalı (≤ 2000 karakter)")
        elif kind == "num" and not (_number(v) and rng[0] <= v <= rng[1]):
            errs.append(f"{key}: {rng[0]}–{rng[1]} aralığında sayı olmalı")
        elif kind == "int" and not (isinstance(v, int) and not isinstance(v, bool) and rng[0] <= v <= rng[1]):
            errs.append(f"{key}: {rng[0]}–{rng[1]} aralığında tam sayı olmalı")
        elif kind == "bool" and not isinstance(v, bool):
            errs.append(f"{key}: true/false olmalı")
        elif kind == "fits" and not (isinstance(v, list) and len(v) == n and all(x in FITS for x in v)):
            errs.append(f"{key}: {n} değerli liste, her biri {', '.join(FITS)}")
        elif kind == "holes" and not (isinstance(v, list) and len(v) == n
                                      and all(x is None or (_number(x) and 1.0 <= x <= 10.0) for x in v)):
            errs.append(f"{key}: {n} değerli liste, her biri null veya 1–10 mm")
        elif kind == "choice" and not (_number(v) and any(abs(v - c) < 1e-9 for c in pred["fit_pair_clearances_mm"])):
            errs.append(f"{key}: kitteki uyum çifti boşluklarından biri olmalı {pred['fit_pair_clearances_mm']}")
    if raw.get("schema") not in (None, SCHEMA):
        errs.append(f"schema: {SCHEMA} olmalı")
    if raw.get("kit_design_sha256") not in (None, pred["kit_design_sha256"]):
        errs.append("kit_design_sha256: bu kayıt başka bir ölçüm kitine ait")
    if errs:
        raise RecordError("; ".join(errs))
    return {k: raw.get(k) for k in FIELDS}


def coupon_step(steps, fits):
    """Smallest CAD clearance step that gave a running fit, or None."""
    return next((s for s, f in zip(steps, fits) if f == "akıcı"), None)


def measured_play(rec: dict, pred: dict) -> dict:
    a, L = rec["axial_float_mm"], pred["lever_mm"]
    tilt = max(0.0, rec["tilt_range_at_tab_mm"] - a) / (2.0 * L)
    return {"axial_mm": a, "tilt_rad": tilt, "tilt_deg": math.degrees(tilt), "lever_mm": L}


def record_sha256(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def apply(d: PrototypeDesign, rec: dict, pred: dict, deploy_moment_per_rpm2=None) -> dict:
    """Design with the measured clearance and play, measured-versus-model rows and warnings (no file is written)."""
    from .checks import joint_play
    sha = record_sha256(rec)
    play = measured_play(rec, pred)
    c = d.connection
    new = with_changes(d, **{"connection.hole_clearance_mm": float(rec["fit_pair_clearance_mm"]),
                             "connection.measured_axial_play_mm": play["axial_mm"],
                             "connection.measured_tilt_deg": play["tilt_deg"],
                             "connection.play_record_sha256": sha})
    model = joint_play(d)
    step = coupon_step(pred["coupon_steps_mm"], rec["coupon_fit"])
    torque = rec["friction_breakaway_n"] * pred["lever_mm"]
    span = d.planform.tip_radius_mm - c.hinge_radius_mm
    warnings = []
    kit = with_changes(d, name=pred["kit_design_name"],
                       **{"connection.hole_clearance_mm": pred["model_play"]["radial_play_mm"],
                          "connection.measured_axial_play_mm": None, "connection.measured_tilt_deg": None,
                          "connection.play_record_sha256": None})
    if kit.identity != pred["kit_design_sha256"]:
        warnings.append("Bu tasarım ölçülen kit tasarımı değil (kimlik farklı): ölçülen boşluk başka bir geometriye "
                        "aktarılıyor ve yalnız yaklaşık; bu tasarımın uyum çiftini basıp ölçün.")
    if rec["tilt_range_at_tab_mm"] < rec["axial_float_mm"]:
        warnings.append("Yük deliğindeki düşey hareket Δ eksenel boşluktan küçük: ölçümü tekrarlayın (eğilme 0 alındı).")
    if rec["axial_float_mm"] == 0 or play["tilt_rad"] == 0:
        warnings.append("Sıfır boşluk ölçüldü: ölçüm çözünürlüğünü kontrol edin; boşluklu açıklık kontrolü sıfır boşlukla "
                        "çalışır.")
    if not rec["stop_seats"] or rec["stop_gap_mm"] > 0.05:
        warnings.append(f"Açık stop oturmuyor (aralık {rec['stop_gap_mm']:.2f} mm): açık konumda yükü lug/pim taşır ve "
                        "hizalama modelden sapar; burun/ped yüzlerini düzeltin veya stop ölçüsünü yeniden basın.")
    if step is None:
        warnings.append("Kupon: hiçbir delik akıcı geçme vermedi; kuponu daha geniş adımlarla yeniden basın.")
    elif abs(step - rec["fit_pair_clearance_mm"]) > 1e-9:
        warnings.append(f"Kupon en küçük akıcı geçmeyi {step:.2f} mm gösteriyor, uyum çifti {rec['fit_pair_clearance_mm']:.2f} mm "
                        "ile basılmış: ölçülen boşluk bu farkı içerir.")
    differs = [name for name, a, b in (("pim Ø", c.pin_diameter_mm, pred["pin_diameter_mm"]),
                                       ("lug aralığı", c.lug_gap_mm, pred["lug_gap_mm"]),
                                       ("lug yarıçapı", c.boss_radius_mm, pred["boss_radius_mm"]))
               if abs(a - b) > 1e-6]
    differs += [f"{n} lug kalınlığı" for n, a, b in zip(("proksimal", "distal"), d.lug_thicknesses_mm,
                                                       pred["lug_thicknesses_mm"]) if abs(a - b) > 0.5]
    if differs:
        warnings.append("Ölçülen boşluk farklı bağlantı ölçülerine aktarıldı (" + ", ".join(differs) + "): yaklaşık; "
                        "bu bağlantıyla yeni bir uyum çifti basıp ölçün.")
    need = -d.connection.stowed_angle_deg
    if rec["folded_stop_deg"] is not None and rec["folded_stop_deg"] < need:
        warnings.append(f"Ölçülen katlanmış stop {rec['folded_stop_deg']:.0f}° < gerekli {need:.0f}°.")
    masses = [rec["mass_fit_proximal_g"], rec["mass_fit_distal_g"]]
    ratio = [m / p if m is not None and p > 0 else None for m, p in zip(masses, pred["fit_masses_g"])]
    if any(r is not None and abs(r - 1.0) > 0.15 for r in ratio):
        warnings.append("Uyum çifti kütlesi modelden %15'ten fazla sapıyor: baskı modelini (yoğunluk, duvar, doluluk) "
                        "ölçülen kütleye göre düzeltin.")
    hole = rec["coupon_hole_mm"] or [None] * len(pred["coupon_steps_mm"])
    k = next((i for i, s in enumerate(pred["coupon_steps_mm"]) if abs(s - rec["fit_pair_clearance_mm"]) < 1e-9), None)
    rows = [
        _row("Pim çapı", c.pin_diameter_mm, rec["pin_measured_diameter_mm"], "mm"),
        _row("Kupon: en küçük akıcı geçme", c.hole_clearance_mm, step, "mm", "CAD çapsal boşluğu"),
        _row("Basılı delik Ø (uyum çifti boşluğunda)", pred["pin_diameter_mm"] + rec["fit_pair_clearance_mm"],
             hole[k] if k is not None else None, "mm"),
        _row("Proksimal lug kalınlığı", pred["lug_thicknesses_mm"][0], rec["lug_thickness_proximal_mm"], "mm"),
        _row("Distal lug kalınlığı", pred["lug_thicknesses_mm"][1], rec["lug_thickness_distal_mm"], "mm"),
        _row("Eksenel boşluk", pred["model_play"]["axial_play_mm"], play["axial_mm"], "mm"),
        _row("Eğilme boşluğu", pred["model_play"]["tilt_deg"], play["tilt_deg"], "°", "model en kötü durum"),
        _row("Uç sarkması (tam distal)", model["tip_droop_mm"], play["axial_mm"] + play["tilt_rad"] * span, "mm"),
        _row("Açık stop aralığı", 0.0, rec["stop_gap_mm"], "mm", "oturuyor" if rec["stop_seats"] else "oturmuyor"),
        _row("Katlanmış stop açısı", pred["folded_stop_deg"], rec["folded_stop_deg"], "°"),
        _row("Sürtünme momenti", None, torque, "N·mm", "sıfır yükte koparma"),
        _row("Uyum çifti kütlesi, proksimal", pred["fit_masses_g"][0], masses[0], "g"),
        _row("Uyum çifti kütlesi, distal", pred["fit_masses_g"][1], masses[1], "g"),
    ]
    rpm = math.sqrt(torque / deploy_moment_per_rpm2) if deploy_moment_per_rpm2 and deploy_moment_per_rpm2 > 0 else None
    return {"design": new, "record_sha256": sha, "play": play, "coupon_step_mm": step, "friction_torque_nmm": torque,
            "self_deploy_rpm": rpm, "rows": rows, "warnings": warnings}


def _row(quantity, model, measured, unit, note=""):
    return {"quantity": quantity, "model": None if model is None else round(float(model), 3),
            "measured": None if measured is None else round(float(measured), 3), "unit": unit, "note": note}


def export_kit(d: PrototypeDesign, folder: Path, clearances=FIT_PAIR_CLEARANCES_MM) -> dict:
    """Write the measurement kit of design ``d``: coupon, fit-pair fixtures per CAD clearance, predictions, record
    template, protocol and SHA-256 sums (all lengths in mm)."""
    import build123d as b3d

    from . import cad, checks, mass
    from .export import _write_mesh
    folder = Path(folder)
    for sub in ("step", "stl", "3mf"):
        (folder / sub).mkdir(parents=True, exist_ok=True)

    written = []

    def write(name, shape):                                     # every file of this run (stale files are not summed)
        b3d.export_step(shape, str(folder / "step" / f"{name}.step"))
        _write_mesh(b3d, shape, folder / "stl" / f"{name}.stl", folder / "3mf" / f"{name}.3mf")
        written.extend(folder / sub / f"{name}.{sub}" for sub in ("step", "stl", "3mf"))

    write("hole_coupon", cad.hole_coupon(d, COUPON_STEPS_MM))
    nominal = min(clearances, key=lambda x: abs(x - d.connection.hole_clearance_mm))
    masses, lever, folded = None, None, None
    for cl in clearances:
        parts = cad.build(with_changes(d, **{"connection.hole_clearance_mm": cl}))
        prox, dist, lever = cad.fit_fixture(parts)
        tag = f"c{cl:.2f}".replace(".", "p")
        write(f"fit_proximal_{tag}", prox)
        write(f"fit_distal_{tag}", dist)
        if cl == nominal:
            masses = (mass.printed(prox, parts.design).mass_g, mass.printed(dist, parts.design).mass_g)
            folded = checks.sweep(parts)["folded_stop_deg"]
    pred = predictions(d, lever, masses, folded, clearances)
    (folder / "predictions.json").write_text(json.dumps(pred, indent=1, ensure_ascii=False), encoding="utf-8")
    (folder / "fit_record_template.json").write_text(template(pred), encoding="utf-8")
    (folder / "design.json").write_text(to_json(d), encoding="utf-8")
    (folder / "README.md").write_text(protocol(d, pred), encoding="utf-8")
    written += [folder / n for n in ("predictions.json", "fit_record_template.json", "design.json", "README.md")]
    sums = [(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(folder).as_posix()) for p in sorted(written)]
    (folder / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for h, n in sums), encoding="utf-8")
    return {"predictions": pred, "files": sums}


def protocol(d: PrototypeDesign, pred: dict) -> str:
    steps = ", ".join(f"Ø{pred['pin_diameter_mm'] + s:.1f}" for s in pred["coupon_steps_mm"])
    cls = ", ".join(f"{c:.1f}" for c in pred["fit_pair_clearances_mm"])
    fields = "\n".join(f"| `{k}` | {v[3]} |" for k, v in FIELDS.items())
    tp, td = pred["lug_thicknesses_mm"]
    return f"""# Measurement kit: {d.name} joint (hole coupon + fit pair)

A measurement prototype for pin fit, joint play, friction and stop seating. It is **not** a selection of this candidate
as the powered propeller, and it qualifies nothing physically. All files are in millimetres. Kit design identity:
`{pred['kit_design_sha256']}`; the record must carry the same identity.

## Parts and print

- `hole_coupon`: a plate of the proximal lug thickness ({tp:.2f} mm) with holes {steps} (k notches beside hole k).
- `fit_proximal_cX` / `fit_distal_cX`: the joint with a CAD diametral hole clearance of X mm ({cls}). The proximal stub
  has a flat clamp block; the distal stub has a flat load tab with a Ø3.2 hole {pred['lever_mm']:.1f} mm from the pin axis
  on the span line through the pin.
- Print everything with the rotor plane on the bed (z up), the same orientation as the full parts, with the settings you
  will use for the full blade. Record printer, material, nozzle, layer, walls and infill.
- Hardware per fit pair: one pin {d.hardware.pin_standard}, two DIN 433 washers (Ø{d.hardware.washer_id_mm:g} ×
  Ø{d.hardware.washer_od_mm:g} × {d.hardware.washer_thickness_mm:g} mm), one DIN 6799 E-clip; pin length under the head
  {d.pin_length_mm:.1f} mm. Measure the actual pin diameter.
- The joint dimensions of this kit (pin Ø, R_b, lug gap) are those of every candidate, but its lugs
  ({tp:.2f} / {td:.2f} mm) are thicker than a 6 mm-offset candidate's. Hole-limited tilt scales roughly with 1/t, so
  measured play transfers to such a design only approximately (the app warns).

## Sequence and measurements

1. **Coupon.** Push the real pin through every hole by hand. Rate each hole: `girmez` (does not enter), `sıkı` (turns
   only with force), `akıcı` (turns freely, no visible wobble), `boşluklu` (visible wobble). Optionally measure each hole
   with pin gauges or drill blanks.
2. **Fit pair.** Print the fit pair whose clearance equals the smallest `akıcı` step (or the nearest exported one) and
   assemble it with the pin set. Record which one you printed (`fit_pair_clearance_mm`).
3. **Dimensions.** Measure both lug thicknesses at the boss with calipers (model {tp:.2f} / {td:.2f} mm).
4. **Axial float a.** Clamp the proximal block in a vise, rotor plane level. Move the distal lug up and down along the pin;
   measure the free movement at the boss (dial indicator or feeler gauges). Model: {pred['lug_gap_mm']:.2f} mm.
5. **Tilt.** Hang/push a known load (about 2 N) up and then down at the tab hole; measure the total vertical movement Δ
   of the tab at the hole. Tilt φ = max(0, Δ − a) / (2 L), L = {pred['lever_mm']:.1f} mm. Model (worst case):
   {pred['model_play']['tilt_deg']:.2f}°.
6. **Friction.** Rotor plane level, distal open on its stop. Pull at the tab hole with a spring scale, horizontally and
   perpendicular to the lever, toward the fold direction (toward the trailing edge); record the force at which folding
   starts. Torque T = F L.
7. **Stop seating.** Hold the distal open by hand; check the nose–pad contact with a 0.05 mm feeler and against light.
   Record the gap and whether the faces seat flat.
8. **Folded stop.** Fold until the nose stops; measure the travel with a protractor (model
   {pred['folded_stop_deg'] if pred['folded_stop_deg'] is not None else 'n/a'}°).
9. **Masses.** Weigh both fit parts without hardware (model {pred['fit_masses_g'][0]:.2f} / {pred['fit_masses_g'][1]:.2f} g
   with {pred['print_model']['material']}, walls {pred['print_model']['wall_mm']} mm, infill
   {pred['print_model']['infill_fraction']:.0%}).

## Record

Copy `fit_record_template.json`, fill every required field and load it in *Prototip → Ölçüm prototipi* (or call
`pyfoldable.prototype.fit.parse` / `apply`). Unknown keys, missing or out-of-range values and a record of another kit are
refused. The measured play then replaces the worst-case model play in the full-travel clearance check of the design the
record is applied to; the measured clearance becomes its hole clearance.

| Field | Meaning |
|---|---|
{fields}

Limits: zero-load friction only (pin friction under centrifugal load is not measured); static play, not fatigue or
creep; one print, one pin. Physical qualification: false.
"""
