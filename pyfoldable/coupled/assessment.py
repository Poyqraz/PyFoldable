"""Engineering reading of a coupled deployment record (no solver; restored record only).

Separates what the record can support from what its assumptions set:

* *Contact events*: impact rate and kinetic energy at the first stop contact after release, the
  centrifugal energy bound m Ω² r_h c_g (1 − cos θ₀) (constant speed, aerodynamic and damping moments
  neglected), the hinge angular-impulse balance over the whole contact interval (a resolved-contact
  check that does not differentiate across the non-smooth stop law), the apparent restitution and the
  peak stop torque next to the undamped penalty estimate |θ̇| √(k J_h).
* *Shaft exchange*: the net angular impulse (drive minus aerodynamic shaft torque) across the contact,
  compared with the distal segments' change of angular momentum about the shaft,
  Σ [J_cg (Ω + θ̇) + m ((r_h² + c_g² + 2 r_h c_g cos θ) Ω + (c_g² + r_h c_g cos θ) θ̇)]. The impulse is a
  property of the mechanism (a real drive turns it into a speed dip or a torsional load); the peak drive
  torque is set by how quickly the stop arrests the distal part (stop stiffness, time step) and by the
  ideal, infinitely stiff prescribed drive. Hub/proximal inertia is not in this balance, so a speed
  change during the contact (ramp) leaves a residual.
* *Output classes*: comparative (same assumptions, compare between cases), preliminary (physics-based,
  scales with declared mechanics: becomes a sizing input once those are measured), illustrative (set by
  an assumed law or an idealised boundary condition) and numerical checks.
"""
from __future__ import annotations

import math

CLASSES = {
    "comparative": "Karşılaştırmalı: aynı varsayımlarla vakalar arasında karşılaştırılabilir",
    "preliminary": "Ön karar: fiziğe dayalı, beyan edilen mekaniğe ölçeklenir; ölçülmüş değerlerle boyutlandırma girdisi olur",
    "illustrative": "Gösterim: varsayılan bir yasa veya ideal sınır koşulu belirler; boyutlandırmada kullanılmaz",
    "numerical_check": "Sayısal denetim: çözümün iç tutarlılığı",
}


def _mech(row):
    case = row["run_definition"]["case"]
    m = case["mechanics"]
    mass, cg = m["distal_mass_kg"], m["distal_cg_from_hinge_m"]
    return case, m, mass, cg, m["distal_inertia_cg_kg_m2"] + mass * cg * cg, case["geometry"]["hinge_radius_m"]


def _valid(row):
    return row["series"][:row["execution"]["valid_prefix_windows"]]


def _release_index(s):
    if not s or not s[0]["latch_active"]:
        return None
    return next((i for i, r in enumerate(s) if not r["latch_active"]), None)


def _rhs(r, b):
    return (r["hinge_aero_torque_nm"][b] + r["hinge_law_torque_nm"][b] + r["centrifugal_hinge_moment_derived_nm"][b]
            + r.get("frame_acceleration_hinge_moment_derived_nm", [0.0] * len(r["theta_deg"]))[b])


def _contact_interval(s, start, b):
    j0 = next((i for i in range(start, len(s)) if s[i]["contact_active"][b]), None)
    if j0 is None or j0 == 0:
        return None
    j1 = j0
    while j1 + 1 < len(s) and s[j1 + 1]["contact_active"][b]:
        j1 += 1
    if j1 + 1 >= len(s):
        return None  # contact not finished inside the valid prefix
    return j0, j1


def contact_events(row) -> list[dict]:
    """First stop contact after release, per blade (empty when there is no release or no finished contact)."""
    s = _valid(row)
    rel = _release_index(s)
    if rel is None:
        return []
    case, m, mass, cg, jh, rh = _mech(row)
    dt = case["dt_s"]
    out = []
    for b in range(len(s[0]["theta_deg"])):
        iv = _contact_interval(s, rel, b)
        if iv is None:
            continue
        j0, j1 = iv
        a, z = j0 - 1, j1 + 1
        rate_in, rate_out = s[a]["theta_rate_rad_s"][b], s[z]["theta_rate_rad_s"][b]
        th0 = math.radians(s[rel - 1]["theta_deg"][b]) if rel > 0 else math.radians(s[rel]["theta_deg"][b])
        w = s[a]["rpm"] * math.pi / 30.0
        bound = mass * w * w * rh * cg * (1.0 - math.cos(th0))
        dl = jh * (rate_out - rate_in)
        imp = sum(0.5 * (_rhs(s[i], b) + _rhs(s[i + 1], b)) * dt for i in range(a, z))
        energy = 0.5 * jh * rate_in * rate_in
        out.append({
            "blade": b, "release_window": s[rel]["window"], "first_contact_window": s[j0]["window"],
            "contact_windows": j1 - j0 + 1, "release_to_contact_s": s[j0]["time_s"] - s[rel]["time_s"],
            "release_fold_deg": math.degrees(th0), "rpm_at_contact": s[a]["rpm"],
            "impact_rate_rad_s": rate_in, "rebound_rate_rad_s": rate_out,
            "apparent_restitution": -rate_out / rate_in if rate_in else None,
            "declared_restitution": m.get("stop_restitution"),
            "impact_energy_j": energy, "centrifugal_energy_bound_j": bound,
            "energy_ratio": energy / bound if bound > 0 else None,
            "hinge_angular_momentum_change_n_m_s": dl, "hinge_impulse_n_m_s": imp,
            "impulse_balance_relative_residual": abs(imp - dl) / abs(dl) if dl else None,
            "peak_stop_torque_nm": max(abs(s[i].get("hinge_contact_torque_nm", s[i]["hinge_law_torque_nm"])[b])
                                       for i in range(j0, j1 + 1)),
            "penalty_peak_estimate_nm": abs(rate_in) * math.sqrt(m["stop_stiffness_nm_per_rad"] * jh),
        })
    return out


def shaft_exchange(row) -> dict | None:
    """Net angular impulse of the prescribed drive across the first contact of all blades (and, separately,
    during the opening swing before it), against the distal segments' change of angular momentum about the
    shaft. Only the contact phase is balanced; the swing impulse has the opposite sign."""
    s = _valid(row)
    rel = _release_index(s)
    if rel is None:
        return None
    nb = len(s[0]["theta_deg"])
    ivs = [iv for iv in (_contact_interval(s, rel, b) for b in range(nb)) if iv is not None]
    if not ivs:
        return None
    case, m, mass, cg, _jh, rh = _mech(row)
    dt = case["dt_s"]
    jcg = m["distal_inertia_cg_kg_m2"]
    a, z = min(iv[0] for iv in ivs) - 1, max(iv[1] for iv in ivs) + 1
    # Window convention of the record: each window's torque is the converged value at the end of its own step,
    # so steps a+1..z carry the state from window a to window z (right-rectangle rule). The hinge balance in
    # contact_events integrates the hinge moments with the trapezoid rule instead, because the penalty torque is
    # a smooth function of the state inside the step; both close to <= 0.6 % on the retained records.
    impulse = sum((s[i]["drive_torque_nm"] - s[i]["aero_shaft_torque_nm"]) * dt for i in range(a + 1, z + 1))
    # opening swing (release to the last free window): opposite sign, independent of the stop's restitution
    swing = sum((s[i]["drive_torque_nm"] - s[i]["aero_shaft_torque_nm"]) * dt for i in range(rel, a + 1))

    def distal_momentum(r):
        """Distal segments' angular momentum about the shaft (planar, rigid, hinge at r_h on the rotating arm)."""
        w = r["rpm"] * math.pi / 30.0
        total = 0.0
        for b in range(nb):
            c_th = math.cos(math.radians(r["theta_deg"][b]))
            rate = r["theta_rate_rad_s"][b]
            total += (jcg * (w + rate) + mass * ((rh * rh + cg * cg + 2.0 * rh * cg * c_th) * w
                                                 + (cg * cg + rh * cg * c_th) * rate))
        return total
    dl = distal_momentum(s[z]) - distal_momentum(s[a])
    duration = (z - a) * dt
    return {"from_window": s[a]["window"], "to_window": s[z]["window"], "exchange_duration_s": duration,
            "angular_impulse_n_m_s": impulse, "distal_momentum_change_n_m_s": dl,
            "swing_impulse_n_m_s": swing, "swing_duration_s": (a - rel + 1) * dt,
            "momentum_balance_relative_residual": abs(impulse - dl) / abs(dl) if dl else None,
            "speed_change_rpm": s[z]["rpm"] - s[a]["rpm"],
            "equivalent_mean_torque_nm": impulse / duration,
            "peak_drive_torque_nm": max(abs(s[i]["drive_torque_nm"]) for i in range(a, z + 1)),
            "time_step_s": dt}



def _last_turn(seq, dt):
    """Trailing windows that make up one shaft revolution at the recorded speeds (fewer if the history is shorter)."""
    out, turns = [], 0.0
    for r in reversed(seq):
        if turns >= 1.0:
            break
        out.append(r)
        turns += r["rpm"] / 60.0 * dt
    return out[::-1], turns


def _check(row, name):
    return next((c.get("value") for c in row.get("checks", []) if c["name"] == name), None)


def output_classes(row) -> list[dict]:
    """What each deployment output can support, with what governs it (labels in Turkish for the UI)."""
    s = _valid(row)
    out = []

    def add(key, label, value, unit, cls, governed_by):
        out.append({"key": key, "label": label, "value": value, "unit": unit, "class": cls, "governed_by": governed_by})

    if s:
        case = row["run_definition"]["case"]
        last, turns = _last_turn(s, case["dt_s"])
        add("thrust_last_rev_n", f"Son devir itkisi ({len(last)} pencere, {turns:.2f} devir)",
            sum(r["thrust_n"] for r in last) / len(last), "N", "comparative",
            "Polar tablosu, DUST kaldırma çizgisi (rbf yanlılığı ≈ −%1,4; BEM’e göre yöntem farkı), kısa pencere")
        mech, mass, cg, rh = case["mechanics"], case["mechanics"]["distal_mass_kg"], \
            case["mechanics"]["distal_cg_from_hinge_m"], case["geometry"]["hinge_radius_m"]
        w_end = s[-1]["rpm"] * math.pi / 30.0
        th_end = math.radians(s[-1]["theta_deg"][0])
        r_cg = math.hypot(rh + cg * math.cos(th_end), cg * math.sin(th_end))
        add("hinge_pin_centrifugal_load_n", "Menteşe pimi merkezkaç yükü (son pencere)", mass * w_end ** 2 * r_cg, "N",
            "preliminary", "m Ω² r_cg (kanat 1, son penceredeki açıda): kütle ve kütle merkezi belirler; aerodinamik yük ve stop darbe tepkisi hariç; "
            f"beyan: {mech.get('declaration_kind', 'belirtilmemiş')}")
        rel = _release_index(s)
        if rel is not None and rel >= 1:
            latched, lturns = _last_turn(s[:rel], case["dt_s"])
            add("thrust_latched_rev_n", f"Katlı (kilitli) devir itkisi ({len(latched)} pencere, {lturns:.2f} devir)",
                sum(r["thrust_n"] for r in latched) / len(latched), "N",
                "comparative", "Kesit durumları ve polar tablosu; katlı dış parçanın 2B polar temsili (süpürme açısı)")
    for ev in contact_events(row)[:1]:  # blade 1; all blades are in contact_events()
        add("release_to_contact_s", "Serbest bırakmadan stop temasına süre (kanat 1)", ev["release_to_contact_s"], "s",
            "preliminary", "m·c_g, J_h, Ω, r_h, başlangıç katlanması; aerodinamik moment küçük katkı")
        add("impact_rate_rad_s", "Temas öncesi açılma hızı θ̇ (kanat 1)", ev["impact_rate_rad_s"], "rad/s", "preliminary",
            "Ω √(2 m r_h c_g (1 − cos θ₀) / J_h) ile ölçeklenir; aerodinamik ve sönüm küçük katkı")
        jh = ev["impact_energy_j"] * 2.0 / ev["impact_rate_rad_s"] ** 2 if ev["impact_rate_rad_s"] else 0.0
        add("incoming_hinge_momentum_n_m_s", "Temas öncesi menteşe açısal momentumu J_hθ̇", jh * ev["impact_rate_rad_s"],
            "N·m·s", "preliminary", "J_h ve çarpma hızı; geri sekme katsayısından bağımsız")
        add("impact_energy_j", "Stop çarpma enerjisi ½J_hθ̇²", ev["impact_energy_j"], "J", "preliminary",
            "Merkezkaç potansiyeli m Ω² r_h c_g (1 − cos θ₀): J_h’den bağımsız; statik moment m·c_g belirler")
        add("energy_ratio", "Çarpma enerjisi / merkezkaç sınırı", ev["energy_ratio"], "-", "preliminary",
            "Aerodinamik, sönüm ve rampa katkısı (1’den fark)")
        add("hinge_angular_momentum_change_n_m_s", "Temasta menteşe açısal momentum değişimi",
            ev["hinge_angular_momentum_change_n_m_s"], "N·m·s", "illustrative",
            "(1 + e)·J_hθ̇: varsayılan geri sekme katsayısı e çarpanı belirler")
        add("peak_stop_torque_nm", "Tepe stop momenti", ev["peak_stop_torque_nm"], "N·m", "illustrative",
            f"Varsayılan stop rijitliği ve sönümü (≈ |θ̇|√(kJ_h) = {ev['penalty_peak_estimate_nm']:.1f} N·m sönümsüz)")
        add("rebound_rate_rad_s", "Geri sekme hızı", ev["rebound_rate_rad_s"], "rad/s", "illustrative",
            f"Varsayılan geri sekme katsayısı e = {ev['declared_restitution']}")
        add("impulse_balance_relative_residual", "Temas boyunca itme dengesi kalıntısı", ev["impulse_balance_relative_residual"],
            "-", "numerical_check", "J_hΔθ̇ = ∫ΣM dt (temas aralığı); noktasal kalıntıdan farklı olarak sıçramayı türevlemez")
    sh = shaft_exchange(row)
    if sh is not None:
        add("swing_impulse_n_m_s", "Açılma salınımında mile aktarılan açısal itme", sh["swing_impulse_n_m_s"], "N·m·s",
            "preliminary", "Dış parçaların dışa açılması (m, c_g, r_h, Ω, θ₀); geri sekmeden bağımsız; temastaki itmeyle zıt işaretli")
        add("angular_impulse_n_m_s", "Temas boyunca mile aktarılan açısal itme", sh["angular_impulse_n_m_s"], "N·m·s",
            "illustrative", "≈ (1 + e)·Σ(J_h + m r_h c_g)θ̇: varsayılan geri sekme katsayısı çarpanı belirler; gerçek tahrikte "
            "devir düşüşü/burulma yükü girdisi")
        add("peak_drive_torque_nm", "Tepe tahrik torku", sh["peak_drive_torque_nm"], "N·m", "illustrative",
            "Sonsuz rijit öngörülen devir ve varsayılan stop (temas süresi); zaman adımına bağımlılığı sınanmadı; "
            "mil yükü tahmini değildir")
        add("momentum_balance_relative_residual", "Mil açısal momentum dengesi kalıntısı", sh["momentum_balance_relative_residual"],
            "-", "numerical_check", "Net tahrik itmesi = dış parçaların mil etrafındaki momentum değişimi; göbek ataleti dahil "
            f"değil (temas boyunca devir değişimi {sh['speed_change_rpm']:.1f} RPM)")
    pointwise = _check(row, "hinge_balance_contact_phase_relative_residual")
    if pointwise is not None:
        add("pointwise_contact_residual", "Noktasal temas fazı kalıntısı (tanı)", pointwise, "-", "numerical_check",
            "Merkezi fark, türevlenemeyen penaltı yasasının sıçramasını kapsar; temas çözünürlüğünü itme dengesi gösterir")
    return out
