"""Measurement prototype and model update: hole coupon + short joint-fit pair of one candidate, printed and measured.

Sequence (``README.md`` written by ``export_kit``): print the hole coupon, pick the smallest step that gives a running
fit with the real pin, print the fit pair with that CAD clearance (a pair is exported for every coupon step and the design clearance), then measure pin
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
import re
from pathlib import Path

from .design import MEASURED_FIELDS, PrototypeDesign, to_json, with_changes

SCHEMA = "pyfoldable.prototype.fit_record/2"   # /2: process identification and hardware stack
MATERIAL_FAMILIES = ("PLA", "ASA", "ABS", "PETG", "other")
MAX_BYTES = 64_000
FITS = ("girmez", "sıkı", "akıcı", "boşluklu")          # no entry / turns only with force / running / visible wobble
COUPON_STEPS_MM = (0.0, 0.1, 0.2, 0.3, 0.4)
FIT_PAIR_CLEARANCES_MM = (0.1, 0.2, 0.3)

# key: (kind, (lo, hi) or None, required, meaning)
FIELDS = {
    "schema": ("text", None, True, "kayıt şeması"),
    "kit_design_sha256": ("text", None, True, "ölçüm kitinin tasarım kimliği (predictions.json)"),
    "print_printer": ("text", None, True, "yazıcı modeli"),
    "print_material_family": ("family", None, True, "malzeme ailesi: " + " / ".join(MATERIAL_FAMILIES)),
    "print_filament_product": ("text", None, True, "filament ürünü (ör. Eco Smart Standard PLA)"),
    "print_filament_manufacturer": ("text", None, False, "filament üreticisi (doğrulanmadıysa null)"),
    "print_filament_lot": ("text", None, False, "renk / parti numarası"),
    "print_plate": ("text", None, False, "baskı tablası (ör. Textured PEI)"),
    "print_slicer": ("text", None, True, "dilimleyici ve sürümü"),
    "print_project_sha256": ("sha256", None, False, "basılan Bambu Studio projesinin SHA-256 özeti"),
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
    "pin_grip_length_mm": ("num", (3.0, 40.0), True, "pimin kafa altından kanalın yakın kenarına ölçülen boyu [mm]"),
    "washer_stack_mm": ("num", (0.0, 5.0), True, "yığındaki pul + şim toplam ölçülen kalınlığı [mm]"),
    "hardware_source": ("text", None, False, "pim/pul/segman tedarikçisi ve parça numaraları"),
    "print_changes": ("text", None, False, "önerilen ayarlardan farklar (destek, brim, telafiler, hız, profil)"),
    "measurement_resolution_mm": ("num", (0.001, 0.5), True, "boşluk ölçümünde kullanılan aletin çözünürlüğü [mm]"),
    "repeat_count": ("int", (1, 50), True, "eksenel boşluk ve Δ ölçümlerinin tekrar sayısı (birden çok uyum çiftinde "
                                           "toplam)"),
    "axial_float_spread_mm": ("num", (0.0, 3.0), False, "tekrarlar arasında eksenel boşluğun aralığı (en büyük − en küçük) [mm]"),
    "tilt_range_spread_mm": ("num", (0.0, 20.0), False, "tekrarlar arasında Δ'nın aralığı [mm]"),
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
        "washer_thickness_mm": d.hardware.washer_thickness_mm,
        "pin_grip_mm": d.stack_thickness_mm + 2 * d.hardware.washer_thickness_mm,   # head underside → groove start
        "declared_process": process_label(d),
        "print_model": {"material": d.print_model.material, "wall_mm": d.print_model.wall_mm,
                        "infill_fraction": d.print_model.infill_fraction, "layer_mm": d.print_model.layer_mm},
    }


def template(pred: dict, prefill: dict | None = None) -> str:
    """Empty record of the kit; ``prefill`` sets confirmed setup fields only (physical measurements stay null)."""
    rec = {k: None for k in FIELDS}
    rec.update(schema=SCHEMA, kit_design_sha256=pred["kit_design_sha256"], notes="",
               coupon_fit=[None] * len(pred["coupon_steps_mm"]), coupon_hole_mm=[None] * len(pred["coupon_steps_mm"]))
    rec.update({k: v for k, v in (prefill or {}).items() if k in FIELDS and v is not None})
    return json.dumps(rec, indent=1, ensure_ascii=False)


def declared_prefill(d) -> dict:
    """The setup the design declares and the owner confirmed: printer, material family, filament product. Nozzle,
    plate, manufacturer and every process value actually used are left for the operator."""
    pm = d.print_model
    return {"print_printer": pm.printer, "print_material_family": pm.material, "print_filament_product": pm.filament}


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
        elif kind == "family" and v not in MATERIAL_FAMILIES:
            errs.append(f"{key}: {', '.join(MATERIAL_FAMILIES)} biri olmalı")
        elif kind == "sha256" and not (isinstance(v, str) and re.fullmatch(r"[0-9a-fA-F]{64}", v.strip())):
            errs.append(f"{key}: 64 onaltılık karakterli SHA-256 olmalı")
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
        errs.append(f"schema: {SCHEMA} olmalı (eski şemadaki kayıtlar süreç alanlarıyla yeniden girilmeli)")
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


D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}


def uncertainty(rec: dict, pred: dict) -> dict:
    """Standard uncertainties of the measured play and of one printed surface's z.

    - reading: each play value is a difference of two readings with resolution r: u = r/√12·√2;
    - spread: with n repeats (over one or more printed pairs) the range R gives s = R/d₂(n) (range method), the
      variation a new print can show, so it is not divided by √n;
    - tilt: u_φ = √(u_Δ² + u_a²)/(2L);
    - print variation of one surface: max(layer/√12, largest measured lug-thickness deviation/√3).
    The verdict uses the expanded margin k·√(u_a² + (s u_φ)² + 2 u_print²) at each distance s (``checks.gap_with_play``).
    """
    reading = rec["measurement_resolution_mm"] / math.sqrt(12.0) * math.sqrt(2.0)
    n = rec["repeat_count"]

    def spread(key):
        r = rec.get(key)
        return r / D2[min(n, 10)] if n >= 2 and r else 0.0
    ua = math.hypot(reading, spread("axial_float_spread_mm"))
    ud = math.hypot(reading, spread("tilt_range_spread_mm"))
    dev = max(abs(rec["lug_thickness_proximal_mm"] - pred["lug_thicknesses_mm"][0]),
              abs(rec["lug_thickness_distal_mm"] - pred["lug_thicknesses_mm"][1]))
    layer = rec["print_layer_mm"]
    return {"axial_mm": ua, "tilt_rad": math.hypot(ud, ua) / (2.0 * pred["lever_mm"]),
            "print_z_mm": max(layer / math.sqrt(12.0), dev / math.sqrt(3.0)), "k": 2.0}


def process_label(d) -> str:
    pm = d.print_model
    return (f"{pm.printer or 'yazıcı ?'} · {pm.nozzle_mm:g} mm nozul · {pm.material} {pm.filament or 'filament ?'} · "
            f"{pm.layer_mm:g} mm katman · {pm.wall_loops} duvar · %{pm.infill_fraction * 100:.0f} doluluk")


def record_process_label(rec) -> str:
    return (f"{rec['print_printer']} · {rec['print_nozzle_mm']:g} mm nozul · {rec['print_material_family']} "
            f"{rec['print_filament_product']} ({rec.get('print_filament_manufacturer') or 'üretici ?'}) · "
            f"{rec['print_layer_mm']:g} mm katman · {rec['print_walls']} duvar · %{rec['print_infill_fraction'] * 100:.0f} doluluk")


def process_differences(d, rec) -> list[str]:
    """Where the specimen's print process differs from the process the design declares (empty: same process)."""
    pm, out = d.print_model, []
    same = lambda a, b: (a or "").strip().casefold() == (b or "").strip().casefold()  # noqa: E731
    if pm.printer is None:
        out.append("tasarım yazıcı bildirmiyor")
    elif not same(pm.printer, rec["print_printer"]):
        out.append(f"yazıcı {rec['print_printer']} ≠ tasarım {pm.printer}")
    if abs(rec["print_nozzle_mm"] - pm.nozzle_mm) > 1e-6:
        out.append(f"nozul {rec['print_nozzle_mm']:g} ≠ {pm.nozzle_mm:g} mm")
    if rec["print_material_family"] != pm.material:
        out.append(f"malzeme {rec['print_material_family']} ≠ tasarım {pm.material}")
    if pm.filament is None:
        out.append("tasarım filament bildirmiyor")
    elif not same(pm.filament, rec["print_filament_product"]):
        out.append(f"filament {rec['print_filament_product']} ≠ tasarım {pm.filament}")
    if abs(rec["print_layer_mm"] - pm.layer_mm) > 1e-6:
        out.append(f"katman {rec['print_layer_mm']:g} ≠ {pm.layer_mm:g} mm")
    if rec["print_walls"] != pm.wall_loops:
        out.append(f"duvar sayısı {rec['print_walls']} ≠ {pm.wall_loops}")
    if abs(rec["print_infill_fraction"] - pm.infill_fraction) > 0.005:
        out.append(f"doluluk {rec['print_infill_fraction']:.2f} ≠ {pm.infill_fraction:.2f}")
    if (rec.get("print_changes") or "").strip():
        out.append(f"önerilen ayarlardan fark bildirildi: {rec['print_changes'].strip()[:200]}")
    return out


def record_sha256(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def apply(d: PrototypeDesign, rec: dict, pred: dict, deploy_moment_per_rpm2=None) -> dict:
    """Design with the measured clearance and play, measured-versus-model rows and warnings (no file is written)."""
    from .checks import joint_play
    sha = record_sha256(rec)
    play = measured_play(rec, pred)
    u = uncertainty(rec, pred)
    c = d.connection
    kit = with_changes(d, name=pred["kit_design_name"],
                       **{"connection.hole_clearance_mm": pred["model_play"]["radial_play_mm"],
                          **{f"connection.{k}": None for k in MEASURED_FIELDS}})
    diffs = process_differences(d, rec)
    basis = "direct" if kit.identity == pred["kit_design_sha256"] and not diffs else "transferred"
    new = with_changes(d, **{"connection.hole_clearance_mm": float(rec["fit_pair_clearance_mm"]),
                             "connection.measured_axial_play_mm": play["axial_mm"],
                             "connection.measured_tilt_deg": play["tilt_deg"],
                             "connection.play_record_sha256": sha, "connection.measured_play_basis": basis,
                             "connection.measured_axial_play_u_mm": u["axial_mm"],
                             "connection.measured_tilt_u_deg": math.degrees(u["tilt_rad"]),
                             "connection.print_z_u_mm": u["print_z_mm"],
                             "connection.measured_process": record_process_label(rec)})
    model = joint_play(d)
    step = coupon_step(pred["coupon_steps_mm"], rec["coupon_fit"])
    torque = rec["friction_breakaway_n"] * pred["lever_mm"]
    span = d.planform.tip_radius_mm - c.hinge_radius_mm
    warnings = []
    if diffs:
        warnings.append("Numunenin baskı süreci tasarımın bildirdiği süreçten farklı (" + "; ".join(diffs) + "): ölçüm "
                        "aktarılmış sayılır, boşluk kararı en kötü durum modelinde kalır. Bu malzeme/süreç için yeni "
                        "uyum çifti basıp ölçün.")
    if kit.identity != pred["kit_design_sha256"]:
        warnings.append("Bu tasarım ölçülen kit tasarımı değil (kimlik farklı): ölçülen boşluk aktarılmış sayılır ve "
                        "yalnız keşifte gösterilir; baskı boşluğu kararı en kötü durum modelini kullanır. Karar için bu "
                        "tasarımın kendi uyum çiftini basıp ölçün.")
    grip_need = rec["lug_thickness_proximal_mm"] + rec["lug_thickness_distal_mm"] + rec["washer_stack_mm"]
    float_hw = rec["pin_grip_length_mm"] - grip_need
    res = rec["measurement_resolution_mm"]           # tolerance: readings of four parts plus clip-groove slack
    if float_hw < -max(0.05, 2.0 * res):
        warnings.append(f"Pim tutma boyu kısa: {rec['pin_grip_length_mm']:.2f} mm < lug + pul yığını {grip_need:.2f} mm; "
                        "segman yerine oturmaz. Daha uzun pim kullanın veya pul azaltın.")
    elif abs(float_hw - rec["axial_float_mm"]) > max(0.15, 4.0 * res):
        warnings.append(f"Pim tutma boyundan beklenen eksenel boşluk {float_hw:.2f} mm, ölçülen {rec['axial_float_mm']:.2f} mm: "
                        "ölçümleri ve şimleri kontrol edin.")
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
        _row("Pim tutma boyu (kafa altı → kanal)", pred.get("pin_grip_mm"), rec["pin_grip_length_mm"], "mm",
             "tasarım: lug yığını + iki pul"),
        _row("Eksenel boşluk, donanımdan", pred["lug_gap_mm"], float_hw, "mm", "tutma boyu − ölçülen lug + pul"),
        _row("Sürtünme momenti", None, torque, "N·mm", "sıfır yükte koparma"),
        _row("Eksenel boşluk belirsizliği u", None, u["axial_mm"], "mm", "çözünürlük + tekrar aralığı"),
        _row("Eğilme belirsizliği u", None, math.degrees(u["tilt_rad"]), "°", "çözünürlük + tekrar aralığı"),
        _row("Baskı yüzeyi z belirsizliği u", None, u["print_z_mm"], "mm", "katman / lug kalınlığı sapması"),
        _row("Uyum çifti kütlesi, proksimal", pred["fit_masses_g"][0], masses[0], "g"),
        _row("Uyum çifti kütlesi, distal", pred["fit_masses_g"][1], masses[1], "g"),
    ]
    rpm = math.sqrt(torque / deploy_moment_per_rpm2) if deploy_moment_per_rpm2 and deploy_moment_per_rpm2 > 0 else None
    return {"design": new, "record_sha256": sha, "play": play, "uncertainty": u, "basis": basis,
            "process_differences": diffs, "process": record_process_label(rec),
            "coupon_step_mm": step, "friction_torque_nmm": torque,
            "self_deploy_rpm": rpm, "rows": rows, "warnings": warnings}


def _row(quantity, model, measured, unit, note=""):
    return {"quantity": quantity, "model": None if model is None else round(float(model), 3),
            "measured": None if measured is None else round(float(measured), 3), "unit": unit, "note": note}


def kit_clearances(d: PrototypeDesign) -> tuple:
    """A fit pair for every coupon step (so any coupon result has its own pair) and for the design's clearance."""
    return tuple(sorted({*COUPON_STEPS_MM, round(round(d.connection.hole_clearance_mm / 0.01) * 0.01, 6)}))


def nominal_clearance(d: PrototypeDesign, clearances) -> float:
    """The kit clearance closest to the design clearance (masses and the folded stop are taken from that pair)."""
    return min(clearances, key=lambda x: abs(x - d.connection.hole_clearance_mm))


def export_kit(d: PrototypeDesign, folder: Path, clearances=None) -> dict:
    """Write the measurement kit of design ``d``: coupon, fit-pair fixtures per CAD clearance, predictions, record
    template, protocol and SHA-256 sums (all lengths in mm)."""
    import build123d as b3d

    from . import cad, checks, mass
    clearances = kit_clearances(d) if clearances is None else tuple(clearances)
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
    nominal = nominal_clearance(d, clearances)
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
    (folder / "fit_record_template.json").write_text(template(pred, declared_prefill(d)), encoding="utf-8")
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
- Pin axis along printer Z for every part, with the settings you will use for the full blade. The proximal prints
  upright on its lug's washer-seat face (the stub is trimmed to that plane); the distal prints **inverted** on its
  lug's washer-seat face, so the running face between the lugs is a free top surface and needs no support. Record
  printer, nozzle, plate, filament, layer, walls, infill and every change from the proposed settings.
- Hardware per fit pair: one pin {d.hardware.pin_standard}, two DIN 433 washers (Ø{d.hardware.washer_id_mm:g} ×
  Ø{d.hardware.washer_od_mm:g} × {d.hardware.washer_thickness_mm:g} mm), one DIN 6799 E-clip; pin length under the head
  {d.pin_length_mm:.1f} mm. Measure the actual pin diameter.
- Print orientation (as the full parts): {d.print_model.orientation}
- Joint of this kit: δ {d.connection.axial_offset_mm:g} mm, lugs {tp:.2f} / {td:.2f} mm (full depth, 0.2 mm proud of the
  blade), lug gap {d.connection.lug_gap_mm:g} mm, boss radius {d.connection.boss_radius_mm:g} mm, pin Ø{d.connection.pin_diameter_mm:g};
  stop nose {d.connection.nose_depth_mm:g} mm deep reaching {d.connection.nose_extension_mm:g} mm ahead of the leading edge onto a
  {d.connection.pad_depth_mm:g} mm pad.
- Play measured on this kit is **direct** evidence only for this design (same identity apart from the hole
  clearance) and then sets its print-clearance verdict with the expanded uncertainty. Applied to any other design it
  is **transferred**: shown for exploration, while that design's verdict keeps the worst-case model.

## Sequence and measurements

1. **Coupon.** Push the real pin through every hole by hand. Rate each hole: `girmez` (does not enter), `sıkı` (turns
   only with force), `akıcı` (turns freely, no visible wobble), `boşluklu` (visible wobble). Optionally measure each hole
   with pin gauges or drill blanks.
2. **Fit pair: one decision.** Print the pair whose clearance equals the **smallest `akıcı` step**; a pair exists for
   every coupon step. If no hole is `akıcı` (all `sıkı`/`girmez`), do not pick a neighbour: generate the exact pair
   with a larger clearance (page *Prototip → Bu tasarımın ölçüm kitini oluştur* with that hole clearance, or
   `fit.export_kit(d, folder, clearances=(c,))`). If even step 0.0 wobbles, print c0.00 and note it. Record which pair
   you printed (`fit_pair_clearance_mm`).
3. **Dimensions.** Measure both lug thicknesses at the boss with calipers (model {tp:.2f} / {td:.2f} mm).
4. **Axial float a.** Clamp the proximal block in a vise, rotor plane level. Move the distal lug up and down along the pin;
   measure the free movement at the boss (dial indicator or feeler gauges). Model: {pred['lug_gap_mm']:.2f} mm.
5. **Tilt.** Hang/push a known load (about 2 N) up and then down at the tab hole; measure the total vertical movement Δ
   of the tab at the hole. Tilt φ = max(0, Δ − a) / (2 L), L = {pred['lever_mm']:.1f} mm. Model (worst case):
   {pred['model_play']['tilt_deg']:.2f}°.
   **Repeat a and Δ at least three times** (reassemble between repeats; if you print two fit pairs, measure both) and
   record the count, the mean values and the range (largest − smallest) of each, with the instrument resolution. The
   verdict subtracts k = 2 times the combined uncertainty (resolution, repeat range, print variation from the lug
   thicknesses) from the worst-case gap.
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


# ------------------------------------------------------------------------------------------- print handoff package
def _oriented(shape, inverted):
    """Print orientation: pin axis along Z; inverted parts turned 180° about X; bounding box moved to x, y, z ≥ 0."""
    import build123d as b3d
    s = shape.rotate(b3d.Axis.X, 180.0) if inverted else shape
    bb = s.bounding_box()
    return s.translate(b3d.Vector(-bb.min.X, -bb.min.Y, -bb.min.Z))


def export_handoff(d: PrototypeDesign, folder: Path, clearances=None) -> dict:
    """Geometry-and-instructions package for a printer operator (not a sliced project): print-oriented 3MF per plate
    (coupon; each fit pair with its two named parts) and STL per part, Turkish print guide with proposed settings,
    assembly and hardware requirements, an operator form for the settings actually used and the measurements, the
    prefilled measurement record, predictions and SHA-256 sums."""
    import build123d as b3d

    from . import cad
    from .export import _write_mesh
    folder = Path(folder)
    clearances = kit_clearances(d) if clearances is None else tuple(clearances)
    for sub in ("3mf", "stl"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    written, dims = [], []
    tag = d.name.replace("13in-", "")

    def write_plate(stem, shapes):
        m = b3d.Mesher()
        for label, s in shapes:
            s.label = label
            m.add_shape(s, linear_deflection=0.01, angular_deflection=0.1)
            bb = s.bounding_box()
            dims.append((label, bb.size.X, bb.size.Y, bb.size.Z))
        m.write(str(folder / "3mf" / f"{stem}.3mf"))
        del m
        _name_3mf_objects(folder / "3mf" / f"{stem}.3mf", [label for label, _ in shapes])
        written.append(folder / "3mf" / f"{stem}.3mf")
        for label, s in shapes:
            part = "" if len(shapes) == 1 else "_" + label.rsplit("_", 1)[1]
            path = folder / "stl" / f"{stem}{part}.stl"
            b3d.export_stl(s, str(path), tolerance=0.01, angular_tolerance=0.1)
            written.append(path)

    coupon = _oriented(cad.hole_coupon(d, COUPON_STEPS_MM), False)
    write_plate("01_kupon", [(f"{tag}_kupon_D{d.connection.pin_diameter_mm:g}+0.0-0.4", coupon)])
    lever = masses = folded = None
    nominal = nominal_clearance(d, clearances)
    for cl in clearances:
        parts = cad.build(with_changes(d, **{"connection.hole_clearance_mm": cl}))
        prox, dist, lever = cad.fit_fixture(parts)
        p = _oriented(prox, False)
        q = _oriented(dist, True)
        q = q.translate(b3d.Vector(p.bounding_box().size.X + 12.0, 0.0, 0.0))
        write_plate(f"02_cift_c{cl:.2f}".replace(".", "p"),
                    [(f"{tag}_cift_c{cl:.2f}_proksimal", p), (f"{tag}_cift_c{cl:.2f}_distal", q)])
        if cl == nominal:
            from . import checks, mass
            masses = (mass.printed(prox, parts.design).mass_g, mass.printed(dist, parts.design).mass_g)
            folded = checks.sweep(parts)["folded_stop_deg"]
    pred = predictions(d, lever, masses, folded, clearances)
    docs = {"BASKI_REHBERI.md": print_guide(d, pred, dims), "MONTAJ_VE_DONANIM.md": assembly_guide(d, pred),
            "BASKI_VE_OLCUM_KAYDI.md": operator_form(d, pred),
            "olcum_kaydi.json": template(pred, declared_prefill(d)),
            "predictions.json": json.dumps(pred, indent=1, ensure_ascii=False), "design.json": to_json(d)}
    for name, text in docs.items():
        (folder / name).write_text(text, encoding="utf-8")
        written.append(folder / name)
    sums = [(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(folder).as_posix()) for p in sorted(written)]
    (folder / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for h, n in sums), encoding="utf-8")
    return {"predictions": pred, "files": sums, "dims": dims}


def _name_3mf_objects(path, names):
    """Write object names onto the build items of a 3MF in order (build123d drops labels when it splits shapes)."""
    import os
    import zipfile
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    key = next(n for n in files if n.endswith(".model"))
    xml = files[key].decode("utf-8")
    ids = re.findall(r'<item\b[^>]*?\sobjectid="(\d+)"', xml)
    if len(ids) != len(names):
        raise RuntimeError(f"{path.name}: {len(ids)} build items for {len(names)} names")
    for oid, name in zip(ids, names):
        safe = re.sub(r"[^A-Za-z0-9_.+-]", "_", name)
        tag = re.search(rf'<object\b[^>]*?\sid="{oid}"[^>]*>', xml).group(0)
        named = (re.sub(r'\sname="[^"]*"', f' name="{safe}"', tag) if re.search(r'\sname="', tag)
                 else tag.replace("<object", f'<object name="{safe}"', 1))
        xml = xml.replace(tag, named, 1)
    files[key] = xml.encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in files.items():
            z.writestr(n, data)
    os.replace(tmp, path)


def print_guide(d, pred, dims) -> str:
    c, pm, tp = d.connection, d.print_model, pred["lug_thicknesses_mm"][0]
    holes = ", ".join(f"Ø{c.pin_diameter_mm + s:.1f}" for s in pred["coupon_steps_mm"])
    rows = "\n".join(f"| `{n}` | {x:.1f} × {y:.1f} × {z:.1f} |" for n, x, y, z in dims)
    pairs = ", ".join(f"`02_cift_c{s:.2f}`".replace(".", "p", 1) for s in pred["fit_pair_clearances_mm"])
    return f"""# {d.name} ölçüm baskısı — operatör rehberi

Bu paket **geometri ve talimat paketidir**: Bambu Studio'da açılıp dilimlenmedi. Dilimlemeyi kendi P1S yapılandırmanızla
siz yapacaksınız; aşağıdaki ayarlar **önerilen** ayarlardır, **kullanılan** ayarları `BASKI_VE_OLCUM_KAYDI.md` formuna yazın.

## İlk basılacak plaka: `3mf/01_kupon.3mf`

Kupon: {tp:.2f} mm kalınlıkta plaka, delikler {holes} mm (deliğin yanında k adet çentik = k. delik). Önce yalnız kuponu
basın, gerçek pimle deneyin, sonra tek bir uyum çifti basın.

## Birim, ölçek, yön

- Birim **mm**, ölçek **%100**. Dosyalar baskı yönünde ve tabla düzlemine (z = 0) oturtulmuş olarak gelir; döndürmeyin,
  otomatik yönlendirme (auto-orient) kullanmayın. Yalnız tabla üzerinde yerini değiştirebilirsiniz.
- Pim ekseni yazıcının **Z** ekseninde. Proksimal parça lug'ının pul yüzü tablada, düz; distal parça **ters çevrilmiş**
  (pul yüzü tablada), böylece iki lug arasındaki çalışma yüzü desteksiz üst yüzey olur.
- Beklenen boyutlar (X × Y × Z, mm) — dilimleyicide aynı değilse ölçek veya birim yanlış içe aktarılmıştır:

| Nesne | Boyut |
|---|---|
{rows}

## Önerilen ayarlar (P1S, 0,4 mm nozul varsayımı)

| Ayar | Önerilen | Not |
|---|---|---|
| Nozul | 0,4 mm | gerçek nozulu doğrulayın |
| Tabla | Textured PEI (P1S standart) | gerçek tablayı doğrulayın |
| Filament | {pm.filament or "?"} | üretici ve etiketi doğrulayın; listede yoksa Generic PLA profili |
| Katman | {pm.layer_mm:g} mm (ilk katman {pm.layer_mm:g} mm) | |
| Duvar | {pm.wall_loops} döngü (≈ {pm.wall_mm:g} mm) | dilim önizlemesinde delik çevresindeki duvar genişliğini kontrol edin |
| Doluluk | %{pm.infill_fraction * 100:.0f} | |
| X-Y delik telafisi | 0 | kupon ham süreci ölçer; telafi kullanırsanız aynı değeri çiftte de kullanın ve yazın |
| X-Y kontur telafisi | 0 | |
| Fil ayağı telafisi | varsayılan | değeri yazın |
| Destek | kupon: yok. Çift: ağaç destek, yalnız tabladan | ters basılan distalde stop burnunun altına tabladan destek gelmesi beklenir; deliklere, lug yüzlerine ve stop burnu/pedinin temas yüzlerine destek gelmemeli |
| Brim | kupon: yok. Çift: 3 mm dış brim | brim kalıntısını lug çevresinden dikkatle alın |
| Ütüleme | kapalı | |
| Dikiş | arka veya hizalı | delik içinde dikiş izi varsa temizlemeyin, kayda yazın |

Delikleri matkap/raybayla açmayın, zımparalamayın: ölçüm, basıldığı haliyle yapılır.

## Kupondan çift seçimi (tek kural)

Pimi her deliğe elle itin ve not edin: `girmez` / `sıkı` (zorla döner) / `akıcı` (serbest döner, gözle görülür
boşluk yok) / `boşluklu`. **En küçük `akıcı` adım** s ise `02_cift_c` + s dosyasını basın. Hazır çiftler: {pairs}.
Hiç `akıcı` yoksa komşu bir çifti seçmeyin; tam boşluklu çift PyFoldable'da üretilir (MONTAJ_VE_DONANIM.md).

Kit kimliği `{pred['kit_design_sha256'][:12]}` — ölçüm kaydı bu kimliği taşır.
"""


def assembly_guide(d, pred) -> str:
    c, h = d.connection, d.hardware
    tp, td = pred["lug_thicknesses_mm"]
    grip = pred["pin_grip_mm"]
    tr = lambda x: f"{x:g}".replace(".", ",")  # noqa: E731
    pin = c.pin_diameter_mm
    proposed = "Önerilen A4/316 Ø4×14 mm pim" if abs(pin - 4.0) < 1e-9 else f"Önerilen Ø{tr(pin)} pim seti ({h.pin_standard})"
    note = ""
    if abs(pin - 4.0) < 1e-9:
        float_14 = 12.5 - grip + c.lug_gap_mm                    # assumed 12.5 mm usable grip of a Ø4×14 pin
        note = (f"\nØ4×14 için not: kafa altı boy 14 mm ise kanal/delik konumu tedarikçi çiziminden okunmalı; tutma boyu "
                f"≈ 12,5 mm çıkarsa nominal yığında eksenel boşluk ≈ {tr(round(float_14, 2))} mm olur ve ≈ "
                f"{tr(round(max(0.0, float_14 - 0.25), 2))} mm şim gerekir (hedef 0,25 mm).\n")
    return f"""# {d.name} uyum çifti — montaj ve donanım

## Donanım kararı açık

{proposed} **henüz uygun bulunmadı**. Montajdan önce aşağıdakiler ölçülüp doğrulanmalı.

| Ölçü | Gereken | Neden |
|---|---|---|
| Pim çapı | Ø{tr(pin)} mm (ölçülen değeri yazın) | kupon ve çift bu çapa göre |
| Kafa çapı | > pul iç çapı {h.washer_id_mm:g} mm, ≤ {2 * (max(h.washer_od_mm, h.clip_od_mm, h.head_diameter_mm) / 2 + 0.3):.1f} mm | pulu tutmalı; tam pervanede havşa içine girmeli |
| Tutma özelliği | DIN 6799 boyut {tr(h.groove_diameter_mm)} kanalı (kanal Ø{tr(h.groove_diameter_mm)}, genişlik ≈ {tr(h.groove_width_mm)}) **veya** pim deliği (kopilya) | tasarım segman + pul varsayar; kopilya delikli pimde boy kuralı deliğin kenarına göre uygulanır |
| Tutma boyu (kafa altı → kanalın yakın kenarı) | ≥ {grip:.2f} mm (= pul {h.washer_thickness_mm:g} + lug {tp:.2f} + aralık {c.lug_gap_mm:g} + lug {td:.2f} + pul {h.washer_thickness_mm:g}) | kısa pim monte edilemez; lugları zımparalamayın |
| Fazla boy | tutma boyu − (ölçülen lug + pul) = 0,1–0,4 mm hedef | fazlası şim (DIN 988 {tr(pin)}×{tr(h.washer_od_mm)}, 0,1/0,2/0,3) veya ek DIN 433 pul ile kapatılır; şimler yığına yazılır |
| Pul | 2 × DIN 433 {tr(h.washer_id_mm)} × {tr(h.washer_od_mm)} × {tr(h.washer_thickness_mm)} | kalınlıkları ölçün |
| Segman | DIN 6799 {tr(h.groove_diameter_mm)} (OD ≈ {tr(h.clip_od_mm)}) | kanala tam oturmalı; pim ucu segmandan ≥ {h.pin_end_mm:g} mm taşmalı |
{note}
## Montaj sırası (alttan üste)

1. Destek ve brim kalıntılarını temizleyin; delik, lug yüzleri, stop burnu ve pedine dokunmayın (zımpara yok).
2. Pim kafası → pul → proksimal lug → distal lug → pul (+ şim) → segman. Distal, proksimalin üstünde (itki tarafı).
3. Distal elle açık stopa (burun pede) dayanmalı; katlanmada ~{pred['folded_stop_deg'] or 0:.0f}°'de burun tekrar temas eder.
4. Zorlayarak montaj yapmayın: pim deliğe girmiyorsa kupon kararını tekrar kontrol edin.

## Kontrol listesi

- [ ] Kupon basıldı, her delik değerlendirildi, en küçük `akıcı` adım seçildi
- [ ] Seçilen boşluktaki çift basıldı (dosya adı kayda yazıldı)
- [ ] Pim çapı, kafa, tutma boyu, kanal, pul ve segman ölçüldü ve kayda yazıldı
- [ ] Lug kalınlıkları ölçüldü (model {tp:.2f} / {td:.2f} mm)
- [ ] Şim kullanıldıysa toplam kalınlık `washer_stack_mm` içine yazıldı
- [ ] Ölçüm protokolü (kit README) uygulandı; eksenel boşluk ve Δ en az 3 kez
"""


def operator_form(d, pred) -> str:
    pm = d.print_model
    rows = [("Yazıcı", pm.printer or "?"), ("Nozul çapı", f"{pm.nozzle_mm:g} mm (doğrulanacak)"),
            ("Tabla", "Textured PEI (doğrulanacak)"), ("Filament ürünü", pm.filament or "?"),
            ("Filament üreticisi / etiket / renk / parti", "(etiket fotoğrafı)"), ("Filament profili", "Generic PLA?"),
            ("Dilimleyici ve sürüm", "Bambu Studio ?"), ("Proje dosyası adı", ""), ("Katman", f"{pm.layer_mm:g} mm"),
            ("Duvar döngüsü", str(pm.wall_loops)), ("Doluluk", f"%{pm.infill_fraction * 100:.0f}"),
            ("X-Y delik / kontur telafisi", "0 / 0"), ("Fil ayağı telafisi", "varsayılan"),
            ("Destek", "kupon yok; çift: ağaç, yalnız tabladan"), ("Brim", "kupon yok; çift 3 mm"),
            ("Akış oranı / basınç ilerlemesi", "profil varsayılanı"), ("Basılan çift", "02_cift_c____")]
    table = "\n".join(f"| {k} | {v} | |" for k, v in rows)
    return f"""# Baskı ve ölçüm kaydı — {d.name} (kit {pred['kit_design_sha256'][:12]})

Önerilen ayarlar ile **gerçekten kullanılan** ayarları ayrı yazın. Bu bilgiler ölçümlerle birlikte PyFoldable'a
girer (`olcum_kaydi.json`): ölçüm ancak aynı yazıcı, nozul, malzeme, filament, katman, duvar ve doluluk ile basılan
tasarıma doğrudan kanıt sayılır; ASA veya değişmiş bir süreç ayrı deneydir.

| Ayar | Önerilen | Kullanılan |
|---|---|---|
{table}

Önerilenden farklar ve gözlemler (destek izi, dikiş, çarpılma, yapışma):

-

Ölçümler: kit README'deki protokol; değerler `olcum_kaydi.json` dosyasına (yazıcı, malzeme ailesi ve filament ürünü
önceden dolduruldu; diğer tüm alanlar operatör/ölçüm içindir).
"""
