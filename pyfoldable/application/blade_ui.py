"""Streamlit wiring of the lofted 3-D blade: design preview, BEM result on the blade, coupled playback.

Geometry: ``visualization.blade_surface`` (catalog profile, declared stations, quarter-chord stacking,
coupled-model fold convention). Results: ``visualization.blade_results`` strips. Contacts:
``visualization.fold_interference`` (display screening; not GEOM-03/04 qualification).
"""
from __future__ import annotations

import csv
import io
import math

import streamlit as st

from . import blade_geometry as bg
from . import blade_views as bv
from pyfoldable.visualization import blade_results as br
from pyfoldable.visualization import blade_surface as bs
from pyfoldable.visualization import fold_interference as fi

CACHE = "_blade3d_cache"
CONVENTION = ("dönüş +Z etrafında, katlanma firar kenarı tarafına (bağlaşık model, 2,5B önizleme ve GEOM-01/03/04 "
              "ile aynı konvansiyon)")


def _rui():
    from . import research_ui
    return research_ui


def _cache():
    return st.session_state.setdefault(CACHE, {})


def _cached(key, build):
    cache = _cache()
    if key not in cache:
        if len(cache) > 24:
            cache.clear()
        cache[key] = build()
    return cache[key]


def mesh_for(spec, *, n_side=56, dr=0.002, joint="relief"):
    return _cached(("mesh", spec, n_side, dr, joint), lambda: bs.loft(spec, n_side=n_side, dr=dr, joint=joint))


def contacts_for(spec, fold_min_deg):
    return _cached(("contacts", spec, round(fold_min_deg, 6)),
                   lambda: (fi.fold_contacts(spec, joint="relief", fold_min_deg=fold_min_deg),
                            fi.fold_contacts(spec, joint="plane", fold_min_deg=max(fold_min_deg, -30.0))))


def _num(x, digits=4):
    return "—" if x is None else (f"{x:.{digits}g}").replace(".", ",")


def scale_controls(prefix, auto_range, unit, auto_label, ident=""):
    """Colour limits; manual limits are kept per quantity (``ident``), never carried to another unit."""
    rui = _rui()
    mode = rui._choice(st.radio, "Renk ölçeği", ("auto", "manual"), key=prefix + "_scale", default="auto", horizontal=True,
                       display={"auto": auto_label, "manual": "Elle (vakaları karşılaştırmak için)"}.__getitem__)
    if mode == "auto":
        return auto_range
    a, b = st.columns(2)
    key = f"{prefix}_{ident}" if ident else prefix
    lo = rui._field(a.number_input, f"Alt sınır [{unit}]", key + "_lo", float(auto_range[0]), format="%.4g")
    hi = rui._field(b.number_input, f"Üst sınır [{unit}]", key + "_hi", float(auto_range[1]), format="%.4g")
    if hi <= lo:
        st.caption("Üst sınır alt sınırdan büyük olmalı; otomatik aralık kullanılıyor.")
        return auto_range
    return (lo, hi)


def _strip_value(field, r):
    for a, b, v in field.strips:
        if a - 1e-12 <= r <= b + 1e-12:
            return a, b, v
    return None


def strips_csv(field) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["r_in_mm", "r_out_mm", f"{field.key}_{field.unit}", "kind", "source"])
    for a, b, v in field.strips:
        w.writerow([f"{1000 * a:.3f}", f"{1000 * b:.3f}", f"{v:.6g}", field.kind, field.source])
    return out.getvalue()


def _downloads(mesh, name, *, fold_deg=0.0, field=None, transforms=None, frame_note="laboratuvar çerçevesi"):
    """Exports are built on request (they are large) for exactly the shown state."""
    ready = st.session_state.get("_blade3d_exports")
    if st.button("Dışa aktarımları hazırla (STL, VTK, CSV)", key=f"blade3d_export_{name}"):
        stl = bv.stl_bytes(mesh, fold_deg=fold_deg) if transforms is None else _stl_from_transforms(mesh, transforms)
        vtk = bv.vtk_bytes(mesh, fold_deg=fold_deg, field=field) if transforms is None else \
            _vtk_from_transforms(mesh, transforms, field)
        ready = st.session_state["_blade3d_exports"] = (name, stl, vtk)
    if not ready or ready[0] != name:
        return
    a, b, c = st.columns(3)
    a.download_button("Geometri (STL, mm)", ready[1], name + ".stl", "model/stl",
                      help="Analiz edilen yüzeyler (katalog profili, beyan edilen istasyonlar); yeniden oluşturulmuş, CAD "
                           f"değil; {frame_note}.")
    b.download_button("Renkli yüzey (VTK, ParaView)", ready[2], name + ".vtk", "application/octet-stream",
                      help="Bölge, parça, kanat kimliği ve seçilen büyüklük (hücre verisi; sonuç olmayan yüzeyler NaN); "
                           f"{frame_note}.")
    if field is not None:
        f0 = field[0] if isinstance(field, (list, tuple)) else field
        c.download_button("Şerit değerleri (CSV)", strips_csv(f0), name + f"_{f0.key}.csv", "text/csv")


def _posed_blades(mesh, transforms):
    import numpy as np
    moving = mesh.vertex_part == "distal"
    return [np.asarray(t(mesh.vertices, moving)) * 1000.0 for t in transforms]


def _stl_from_transforms(mesh, transforms):
    import numpy as np
    out = io.StringIO()
    out.write(f"solid pyfoldable_{mesh.spec.profile_id}_reconstructed_mm\n")
    sel = mesh.faces[np.isin(mesh.region, ("aero", "joint"))]
    for v in _posed_blades(mesh, transforms):
        tri = v[sel]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
        for t, nn in zip(tri, n):
            out.write(f"facet normal {nn[0]:.6e} {nn[1]:.6e} {nn[2]:.6e}\n outer loop\n")
            out.write("".join(f"  vertex {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n" for p in t))
            out.write(" endloop\nendfacet\n")
    out.write(f"endsolid pyfoldable_{mesh.spec.profile_id}_reconstructed_mm\n")
    return out.getvalue().encode()


def _vtk_from_transforms(mesh, transforms, field):
    text = bv.vtk_bytes(mesh, fold_deg=0.0, field=field).decode()
    head, rest = text.split("POINTS ", 1)
    count_line, rest = rest.split("\n", 1)
    n = int(count_line.split()[0])
    pts = "".join(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n" for v in _posed_blades(mesh, transforms) for p in v)
    rest = rest.split("POLYGONS", 1)[1]
    if n != len(mesh.vertices) * len(transforms):
        raise ValueError("VTK point count does not match the posed blades.")
    return (head + f"POINTS {count_line}\n" + pts + "POLYGONS" + rest).encode()


# ---------------------------------------------------------------- design tab
def design_preview(active, foil, view):
    rui = _rui()
    i = active.inputs
    try:
        spec = bg.spec_from_active(active, foil)
        mesh = mesh_for(spec)
        rep, plane = contacts_for(spec, max(-180.0, min(-0.01, i.stow_limit_deg)))
    except ValueError as exc:
        st.warning("Bu menteşe ekseni lofted görünümde desteklenmiyor (yalnız şafta paralel, çeyrek kirişten geçen eksen)."
                   if "hinge axis" in str(exc) else
                   "Bu konumda saklanan istasyonlardan yüzey çizilemiyor. Menteşe ve istasyon açıklığını kontrol edin.")
        with st.expander("Önizleme teknik ayrıntısı"):
            st.text(str(exc))
        return
    shown = rep.clamp(i.fold_deg)
    st.caption(f"Gösterilen katlanma pozu: {rui._fmt(shown, 1)}°. BEM, ana kanadı tam açık (0°) çözer. Geometri: "
               f"{spec.profile_id} katalog profili, beyan edilen istasyonlar (kord ve burulma yarıçapla doğrusal), "
               f"çeyrek kiriş yığılımı; {CONVENTION}. Yeniden oluşturulmuş yüzey, CAD değil.")
    if shown > i.fold_deg + 1e-9:
        st.warning(f"İstenen poz {rui._fmt(i.fold_deg, 1)}°: tanımlı yüzeyler bu gösterim geometrisinde (eklem bölgesi "
                   f"varsayılan) {rui._fmt(rep.interference_free_deg, 1)}°’den sonra temas eder; poz son temassız açıda "
                   "durduruldu (tanımlı yüzeyler iç içe çizilmez). Daha derin katlanma, tanımlı bir eklem tasarımı (ör. "
                   "eksenel kaydırmalı çatal–dil) gerektirir.")
    revision = st.session_state.get("_research_camera_revision", 0)
    camera = "Üst"
    if view == "3B":
        controls, reset = st.columns((1.5, 1), vertical_alignment="bottom")
        camera = rui._choice(controls.selectbox, "Kamera", tuple(rui.views.CAMERAS), key=f"research_camera_{revision}",
                             default="İzometrik")
        reset.button("Kamerayı sıfırla", on_click=rui._reset_camera)
    at_contact = abs(shown - rep.interference_free_deg) < 0.05
    fig = bv.blade_figure(mesh, fold_deg=shown, contacts=rep if at_contact else None, contact_angle_deg=shown,
                          uirevision=f"{active.identity}:{camera}:{revision}")
    fig.update_layout(scene_camera={**rui.views.CAMERAS[camera], "projection": {"type": "orthographic"}})
    rui._plot(fig, "research_surface" if view == "3B" else "research_plan")
    st.caption("3B için tarayıcıda WebGL gerekir. Plan, aynı yüzeyin üstten dik izdüşümüdür.")
    _contact_summary(rep, plane, mesh)


def _contact_summary(rep, plane, mesh):
    rui = _rui()
    lines = []
    for c in rep.contacts:
        if c.status == "contact":
            lines.append(f"{c.a} ↔ {c.b}: ilk temas {rui._fmt(c.first_contact_deg, 1)}° "
                         f"(nokta {', '.join(rui._fmt(1000 * v, 1) for v in c.point_a)} mm)")
        elif c.status == "in_contact_open":
            lines.append(f"{c.a} ↔ {c.b}: açık konumda bile temas/örtüşme")
        elif c.status == "possible_undefined_geometry":
            lines.append(f"{c.a} ↔ {c.b}: olası temas {rui._fmt(c.first_contact_deg, 1)}° (yüzey verisi olmayan bölge)")
        elif c.status == "possible_hub_radius_only":
            lines.append(f"{c.a} ↔ {c.b}: olası temas {rui._fmt(c.first_contact_deg, 1)}° (göbek yalnız yarıçapla tanımlı)")
    own = plane.pair("distal_1", "proximal_1")
    st.caption(
        "**Katlanma teması (yüzey taraması; bağlaşık model konvansiyonu, katlanma firar kenarı tarafına):** "
        + ("; ".join(lines) if lines else "beyan edilen aralıkta temas yok")
        + f". Tanımlı yüzeyler için temassız katlanma 0° → {rui._fmt(rep.interference_free_deg, 1)}° (eklem bölgesinin "
        f"gösterim yarıçapına bağlıdır; adım {rui._fmt(rep.step_deg, 2)}°, ince kenar geçişleri kaçabilir). Menteşe düzleminde ayrılan aerodinamik "
        + (f"geometri {rui._fmt(own.first_contact_deg, 2)}°’de iç içe girer (firar kenarı tarafında); bu yüzden pivot "
           if own.status == "contact" else "geometri bu aralıkta iç içe girmez; ")
        + f"çevresindeki eklem bölgesi (yarıçap {rui._fmt(1000 * mesh.joint_radius_m, 1)} mm) dış parçayla döner olarak "
        "gösterilir — eklem geometrisi tanımlı değil. Göbek yalnız yarıçapla tanımlı (sonsuz silindir). Gösterim taraması; "
        "GEOM-03/04 niteliklendirmesi değildir.")


# ---------------------------------------------------------------- BEM result on the blade
def bem_on_blade(row):
    rui = _rui()
    st.markdown("**Kanat üzerinde sonuç (3B)**")
    try:
        spec = bg.spec_from_saved_research(row)
        mesh = mesh_for(spec)
        fields = br.bem_fields(row)
    except (ValueError, KeyError, TypeError) as exc:
        st.warning("Bu kayıt için kanat yüzeyi oluşturulamadı; radyal grafikler geçerlidir.")
        with st.expander("Ayrıntı"):
            st.text(str(exc))
        return
    key = rui._choice(st.selectbox, "Gösterilen büyüklük", tuple(fields), key="research_blade_field",
                      default="dthrust_per_span", display=lambda k: f"{fields[k].label} [{fields[k].unit}]")
    f = fields[key]
    vals = [s[2] for s in f.strips]
    crange = scale_controls("research_blade", (min(vals), max(vals)), f.unit, "Bu sonucun aralığı", ident=f.key)
    lo, hi = 1000 * f.strips[0][0], 1000 * f.strips[-1][1]
    r_mm = rui._field(st.slider, "İncelenen kesit r [mm]", "research_blade_radius", round(0.5 * (lo + hi), 1),
                      min_value=round(lo, 1), max_value=round(hi, 1), step=0.5)
    hit = _strip_value(f, r_mm / 1000)
    if hit:
        st.caption(f"r = {rui._fmt(r_mm, 1)} mm → şerit {rui._fmt(1000 * hit[0], 1)}–{rui._fmt(1000 * hit[1], 1)} mm: "
                   f"**{_num(hit[2])} {f.unit}**")
    rui._plot(bv.blade_figure(mesh, fold_deg=0.0, field=f, crange=crange, selected_radius_m=r_mm / 1000,
                              uirevision=f"bem:{row['result_sha256']}"), "research_blade3d")
    st.caption(f"{f.note} Hesaplanan: {f.source}, tam açık rotor (0°). Yeniden oluşturulan: kanat yüzeyi "
               f"({spec.profile_id} katalog profili, kaydın taslağındaki istasyonlar). Gri yüzeyler sonuç taşımaz "
               "(kesit uçları, yüzey verisi olmayan aralıklar).")
    rui._plot(bv.radial_link_figure(f, selected_radius_m=r_mm / 1000, crange=crange, hinge_radius_m=spec.hinge_radius_m),
              "research_blade_radial")
    _downloads(mesh, f"pyfoldable_{spec.profile_id}_{row['result_sha256'][:8]}_bem_{f.key}", field=f,
               frame_note="tam açık, kanat 1 azimut 0")


# ---------------------------------------------------------------- coupled playback
_FRAMES = {"rotor": "Rotorla birlikte (dönmeyen gözlem)", "physical": "Dönen (fiziksel)"}


def coupled_range(row, key):
    return _cached(("crange", row["result_sha256"], key), lambda: br.coupled_range(row, key))


def coupled_spec_mesh(row):
    spec = bg.spec_from_coupled(row)
    return spec, mesh_for(spec)


def field_controls(row, prefix, window, *, allow_none=False):
    rui = _rui()
    blades = row["run_definition"]["case"]["geometry"]["blade_count"]
    per_blade = [br.coupled_fields(row, window, b) for b in range(blades)]
    keys = (("none",) if allow_none else ()) + tuple(per_blade[0])
    key = rui._choice(st.selectbox, "Kanatta gösterilen büyüklük", keys, key=prefix + "_field",
                      default="fz_per_span",
                      display=lambda k: "Yalnız geometri" if k == "none" else f"{per_blade[0][k].label} [{per_blade[0][k].unit}]")
    frame = rui._choice(st.radio, "Görünüm çerçevesi", tuple(_FRAMES), key=prefix + "_frame", default="rotor",
                        horizontal=True, display=_FRAMES.__getitem__)
    if key == "none":
        return None, None, frame
    return [p[key] for p in per_blade], coupled_range(row, key), frame


def coupled_blade_tab(row, root):
    rui = _rui()
    from pyfoldable.coupled import flow
    from . import coupled_views as views
    try:
        spec, mesh = coupled_spec_mesh(row)
    except (ValueError, KeyError) as exc:
        st.error("Kanat yüzeyi bu kayıttan oluşturulamadı: " + str(exc))
        return
    valid = row["series"][:row["execution"]["valid_prefix_windows"]]
    windows = [r["window"] for r in valid]
    if len(windows) < 2:
        st.info("Bu kayıtta oynatılacak yeterli geçerli pencere yok.")
        return
    ev = flow.events(row)
    if st.session_state.get("coupled_blade_window") not in windows:
        st.session_state["coupled_blade_window"] = ev.get("first_contact", windows[-1])
    w = st.select_slider("Kabul edilen pencere", options=windows, key="coupled_blade_window")
    try:
        fields, crange, frame = field_controls(row, "coupled_blade", w)
    except (ValueError, KeyError) as exc:
        st.error("Bu kaydın eleman sonuçları kanada eşlenemedi: " + str(exc))
        return
    f0 = fields[0]
    crange = scale_controls("coupled_blade", crange, f0.unit, "Tüm pencerelerde sabit (bu kayıt)",
                            ident=f"{f0.key}_{row['result_sha256'][:8]}")
    lo, hi = 1000 * f0.strips[0][0], 1000 * f0.strips[-1][1]
    r_mm = rui._field(st.slider, "İncelenen kesit r [mm]", "coupled_blade_radius", round(0.5 * (lo + hi), 1),
                      min_value=round(lo, 1), max_value=round(hi, 1), step=0.5)
    tf = bg.node_transforms(row, w)
    psi = bg.rotor_azimuth(row, w)
    R = 1000 * spec.tip_radius_m
    s = next(r for r in valid if r["window"] == w)
    fig = bv.blade_figure(mesh, field=fields, crange=crange, transforms=tf,
                          view_rotation_rad=-psi if frame == "rotor" else 0.0, selected_radius_m=r_mm / 1000,
                          scene_ranges=((-1.15 * R, 1.15 * R), (-1.15 * R, 1.15 * R), (-0.35 * R, 0.35 * R)),
                          uirevision=f"blade:{row['result_sha256']}:{frame}")
    rui._plot(fig, "coupled_blade3d")
    st.caption(f"Pencere {w} · t = {s['time_s']:.4f} s · {rui._fmt(s['rpm'], 0)} RPM · θ = "
               + " / ".join(rui._fmt(t, 2) + "°" for t in s["theta_deg"])
               + f". Renk ölçeği tüm pencerelerde sabit: {_num(crange[0])} … {_num(crange[1])} {f0.unit} "
               "(vakalar arasında karşılaştırmak için elle sınır seçin).")
    st.caption(f"{f0.note} Hesaplanan: DUST kaldırma çizgisi elemanları (bu pencere). Yeniden oluşturulan: kanat yüzeyi "
               f"({spec.profile_id} katalog profili, kaydın kesitleri) MBDyn gövde durumlarıyla konumlandı. "
               f"Çerçeve: {_FRAMES[frame]}. Eklem bölgesi yalnız gösterimdir.")
    c1, c2 = st.columns(2)
    with c1:
        rui._plot(bv.radial_link_figure(f0, selected_radius_m=r_mm / 1000, crange=crange,
                                        hinge_radius_m=spec.hinge_radius_m), "coupled_blade_radial")
        st.caption("Kanat 1 · seçilen pencere; dikey çizgi seçilen kesit, kesikli çizgi menteşe yarıçapı (açık konum).")
    with c2:
        rui._plot(views.response_timeline_figure(row, w, ev), "coupled_blade_timeline")
    _downloads(mesh, f"pyfoldable_dinamik_{row['result_sha256'][:8]}_w{w}_{f0.key}", field=fields, transforms=tf,
               frame_note="laboratuvar çerçevesi (MBDyn durumları; rotorla birlikte görünüm dışa aktarılmaz)")
    if st.button("Kısa oynatma hazırla (renkli, kaba ağ)", key="coupled_blade_anim",
                 help="Seçilen büyüklükle en çok 40 kabul edilen pencereden tarayıcıda oynatılan kareler."):
        st.session_state["_coupled_blade_anim"] = (row["result_sha256"], f0.key, frame)
    if st.session_state.get("_coupled_blade_anim") == (row["result_sha256"], f0.key, frame):
        rui._plot(animation_figure(row, spec, f0.key, crange, frame), "coupled_blade_anim_fig")
        st.caption("Oynatma kaba ağ kullanır (gösterim); değerler seçilen pencerelerin kaydedilmiş sonuçlarıdır.")


def animation_figure(row, spec, key, crange, frame, max_frames=40):
    import numpy as np
    import plotly.graph_objects as go
    coarse = mesh_for(spec, n_side=20, dr=0.008)
    valid = row["series"][:row["execution"]["valid_prefix_windows"]]
    pick = np.unique(np.linspace(0, len(valid) - 1, min(max_frames, len(valid))).round().astype(int))
    windows = [valid[k]["window"] for k in pick]
    blades = spec.blade_count
    side = np.isin(coarse.region, ("aero", "joint"))
    moving = coarse.vertex_part == "distal"
    R = 1000 * spec.tip_radius_m

    def trace(w):
        tf = bg.node_transforms(row, w)
        rot = -bg.rotor_azimuth(row, w) if frame == "rotor" else 0.0
        vs, fs, vals, base = [], [], [], 0
        for b in range(blades):
            v = bv._rot(np.asarray(tf[b](coarse.vertices, moving)), rot) * 1000.0
            fv = br.face_values(coarse, br.coupled_fields(row, w, b)[key])
            ok = side & np.isfinite(fv)
            vs.append(v); fs.append(coarse.faces[ok] + base); vals.append(fv[ok]); base += len(v)
        v, f = np.vstack(vs), np.vstack(fs)
        return go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2], intensity=np.concatenate(vals),
                         intensitymode="cell", colorscale="Viridis", cmin=crange[0], cmax=crange[1], showscale=True,
                         hoverinfo="skip", name="Sonuç")
    frames = [go.Frame(data=[trace(w)], name=str(w)) for w in windows]
    fig = go.Figure(data=frames[0].data, frames=frames)
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0),
                      scene=dict(xaxis=dict(range=[-1.15 * R, 1.15 * R]), yaxis=dict(range=[-1.15 * R, 1.15 * R]),
                                 zaxis=dict(range=[-0.35 * R, 0.35 * R]), aspectmode="manual",
                                 aspectratio=dict(x=1, y=1, z=0.3)),
                      updatemenus=[dict(type="buttons", x=0, y=0, xanchor="left", yanchor="top", buttons=[
                          dict(label="▶", method="animate", args=[None, dict(frame=dict(duration=120, redraw=True),
                                                                             fromcurrent=True)]),
                          dict(label="❚❚", method="animate", args=[[None], dict(mode="immediate")])])],
                      sliders=[dict(steps=[dict(method="animate", label=str(w),
                                                args=[[str(w)], dict(mode="immediate", frame=dict(redraw=True))])
                                           for w in windows], currentvalue=dict(prefix="Pencere "))])
    return fig
