"""'Görseller': the workspace figures in one place, built only on request. A registry of cards calls the existing
builders (and gallery_figures for the figures no other view draws). Every card names its source and evidence class;
a missing source or a failed build stays visible. No card claims physical qualification."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from . import coupled_views as cv, fold_cycle_views as fcv, gallery_figures as gf
from . import research_ui as rui

SECTIONS = ("Tasarım", "BEM sonucu", "Açılma–kapanma çevrimi", "Dinamik bağlaşık", "Arşiv kanıtı", "Eski örnek boru hattı")
_IDS = dict(zip(SECTIONS, ("design", "bem", "cycle", "coupled", "archive", "legacy")))
SESSION = "oturum sonucu · fiziksel yeterlilik yok"
ARCHIVE = "arşiv kanıtı · değiştirilmez"
LEGACY = "eski örnek boru hattı · sentetik fikstür · tasarım kanıtı değil"
SCREENSHOT = "ekran görüntüsü · belgeleme"
_CACHE, _CACHE_MAX = "_gallery", 24
_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_MAX_FILE_BYTES = 8 * 2**20
_CYCLE_SCOPE = "Öngörülen (dinamik) hareket, mekanik model varsayımlarıyla; yapısal gerilme çözülmedi."
_COUPLED_SCOPE = "Kabul edilen MBDyn/DUST pencereleri; noktalı çizgiler geçerli önek dışıdır."


# ----------------------------------------------------------------------------------------------- archive files
def archive_files(root) -> list:
    base = (Path(root) / "reports").resolve()
    return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())


def archive_path(root, rel) -> Path:
    """Resolved file inside reports/ (links included); anything else is refused."""
    base = (Path(root) / "reports").resolve()
    path = (base / str(rel)).resolve()
    if not str(rel).strip() or base not in path.parents or not path.is_file():
        raise ValueError("Arşiv dosyası reports/ klasörünün içinde olmalı.")
    return path


def _archive_build(ctx):
    path = ctx["file"]
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError("Dosya 8 MB’tan büyük; galeride açılmaz.")
    suffix = path.suffix.lower()
    if suffix in _IMAGES:
        readme = path.parent / "README.md"
        return {"images": [(path.name, path.read_bytes())],
                **({"readme": readme.read_text(encoding="utf-8")} if readme.is_file() else {})}
    if suffix == ".json":
        doc = json.loads(path.read_text(encoding="utf-8"))
        if path.name.startswith("convergence_"):
            return gf.convergence_heatmap(doc)
        return gf.archived_json_figure(path) or {"json": doc}
    data = path.read_bytes()       # by content: raw XFOIL captures (.bin, .dat, .log) are plain text
    try:
        text = None if b"\0" in data else data.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is None:
        raise ValueError("Bu dosya türü galeride gösterilmez (ikili veri).")
    return {"markdown" if suffix == ".md" else "text": text}


# ------------------------------------------------------------------------------------------------------- cards
def _foil(active):
    return next(f for f in active.design.airfoils if f.id == active.inputs.profile)


def _airfoil(ctx):
    from . import research_views
    return research_views.airfoil_figure(_foil(ctx["active"]))


def _design_blade(ctx):
    """Lofted blade at the requested fold pose, stopped at the last contact-free angle as on the Design tab."""
    from . import blade_ui as bu
    i = ctx["active"].inputs
    spec = bu.bg.spec_from_active(ctx["active"], _foil(ctx["active"]))
    rep, _ = bu.contacts_for(spec, max(-180.0, min(-0.01, i.stow_limit_deg)))
    shown = rep.clamp(i.fold_deg)
    return bu.bv.blade_figure(bu.mesh_for(spec), fold_deg=shown, contact_angle_deg=shown,
                              contacts=rep if abs(shown - rep.interference_free_deg) < 0.05 else None)


def _bem_fields(ctx):
    from . import research_design as research, research_views
    label, digits = rui._RADIAL_COLUMNS[ctx["field"]]
    name, _, unit = label.partition(" [")
    return research_views.radial_figure(research.radial_rows(ctx["row"]), ((ctx["field"], name, digits),),
                                        unit.rstrip("]") or "boyutsuz")


def _bem_blade(row):
    """The Analysis blade view's default field (thrust per span) on the record's own reconstructed blade."""
    from . import blade_ui as bu
    return bu, bu.bg.spec_from_saved_research(row), bu.br.bem_fields(row)["dthrust_per_span"]


def _bem_link(ctx):
    bu, spec, f = _bem_blade(ctx["row"])
    return bu.bv.radial_link_figure(f, hinge_radius_m=spec.hinge_radius_m)


def _bem_blade3d(ctx):
    bu, spec, f = _bem_blade(ctx["row"])
    return bu.bv.blade_figure(bu.mesh_for(spec), fold_deg=0.0, field=f)


def _bem_rotation(ctx):
    bu, spec, f = _bem_blade(ctx["row"])
    a, vals = ctx["row"]["aerodynamics"], [s[2] for s in f.strips]
    return bu.bv.bem_rotation_figure(bu.mesh_for(spec, n_side=24, dr=0.006), field=f, crange=(min(vals), max(vals)),
                                     rpm=ctx["row"]["inputs"]["rpm"],
                                     thrust_n=a["thrust_n"], torque_nm=a["torque_nm"], power_w=a["shaft_power_w"])


def _polar(ctx):
    from . import polar_upload, research_design as research
    prepared = research.prepare_aero(ctx["active"], ctx["family"], ctx["repository"])
    return gf.polar_family_figure(polar_upload.inspect_polar_bundle(prepared.polar_run.payload).to_family())


def _envelope(ctx):
    rpm = ctx["active"].inputs.rpm
    return gf.envelope_map(ctx["active"], ctx["family"], rpms=tuple(round(rpm * k / 10) for k in range(4, 17)),
                           inflows=tuple(range(0, 31, 2)))


def _slipstream(ctx):
    from pyfoldable.visualization import bem_flow
    return bem_flow.slipstream_figure(ctx["row"])


def _response(ctx):
    from pyfoldable.coupled import flow
    ev = flow.events(ctx["coupled"])
    return cv.response_timeline_figure(ctx["coupled"], ev.get("first_contact", ev.get("last")), ev)


def _flow(ctx):
    """Verified flow companion of the record and the window shown (first contact, else the last frame)."""
    from pyfoldable.coupled import flow
    from . import coupled_ui
    try:
        fc = coupled_ui._flow(ctx["coupled"], ctx["root"])
    except flow.FlowCompanionError as exc:
        raise ValueError("Akış eki yok: Dinamik bağlaşık > Akış ve tepki sekmesinden oluşturun. "
                         + str(exc).split(": ", 1)[-1]) from exc
    ev = flow.events(ctx["coupled"])
    return fc, flow.nearest_frame(fc, ev.get("first_contact", int(fc.windows[-1])))


def _flow_plane(ctx):
    fc, w = _flow(ctx)
    return cv.flow_plane_figure(ctx["coupled"], fc, w)


def _wake(ctx):
    fc, w = _flow(ctx)
    return cv.wake_radial_figure(ctx["coupled"], fc, w, int(fc.windows[0]))


def _flow_scene(ctx):
    fc, w = _flow(ctx)
    return cv.flow_scene_figure(ctx["coupled"], fc, w)


def _coupled_radial(ctx):
    from . import coupled_ui
    return cv.radial_figure(cv.radial_rows(ctx["coupled"], ctx["window"]), ctx["field"],
                            coupled_ui._RADIAL_LABELS[ctx["field"]])


def _coupled_blade3d(ctx):
    """Blades posed by the MBDyn states of the chosen window, coloured by DUST element thrust per span (rotor frame)."""
    from . import blade_ui as bu
    row, w = ctx["coupled"], ctx["window"]
    spec, mesh = bu.coupled_spec_mesh(row)
    R = 1000 * spec.tip_radius_m
    return bu.bv.blade_figure(mesh, field=[bu.br.coupled_fields(row, w, b)["fz_per_span"] for b in range(spec.blade_count)],
                              crange=bu.coupled_range(row, "fz_per_span"), transforms=bu.bg.node_transforms(row, w),
                              view_rotation_rad=-bu.bg.rotor_azimuth(row, w),
                              scene_ranges=((-1.15 * R, 1.15 * R), (-1.15 * R, 1.15 * R), (-0.35 * R, 0.35 * R)))


def _coupled_animation(ctx):
    from . import blade_ui as bu
    spec, _ = bu.coupled_spec_mesh(ctx["coupled"])
    return bu.animation_figure(ctx["coupled"], spec, "fz_per_span", bu.coupled_range(ctx["coupled"], "fz_per_span"), "rotor")


def _coupled_loads(ctx):
    """Only reads a stored, sealed connection-load companion; deriving one stays on the coupled result page."""
    from pyfoldable.coupled import hinge_loads
    from . import coupled_analysis
    run_dir = coupled_analysis.local_run_dir(ctx["root"], ctx["coupled"])
    comp = hinge_loads.load(run_dir, ctx["coupled"]) if run_dir is not None else None
    if comp is None:
        raise ValueError("Bağlantı yükleri eki yok: Dinamik bağlaşık > Bağlantı yükleri sekmesinden türetin.")
    return fcv.coupled_figure(comp, ctx["coupled"], 0)


_V02 = ("V02 sabit devir koşusu θ = −180° ve T_tip = 0 ile biter (uç tamamen geri katlanmış): bu set çökmüş uç "
        "durumunu gösterir.")
_LEGACY_SOURCE = "configs/foldable/TIP_HINGED_250_V0x.json + data/propellers/apc_202602 (sentetik fikstür)"


def _card(id, section, title, explains, build, *, needs=(), missing="", scope="", cost="light", evidence=SESSION,
          warning=None):
    return dict(id=id, section=section, title=title, explains=explains, build=build, needs=needs, missing=missing,
                scope=scope, cost=cost, evidence=evidence, warning=warning)


_NO_BEM = "Analiz’de BEM çalıştırın veya Karşılaştırma / kayıtlar’dan bir kayıt açın."
_NO_CYCLE = "Analiz’de bir açılma–kapanma çevrimi çalıştırın veya kaydedilmiş bir çevrimi açın."
_NO_COUPLED = "Analiz’de dinamik bağlaşık analiz çalıştırın veya Karşılaştırma / kayıtlar’dan bir kayıt açın."
CARDS = [
    _card("design_airfoil", "design", "Profil kesiti", "Seçili katalog profilinin koordinatları, iki eksen aynı ölçekte.",
          _airfoil, needs=("active",), missing="Tasarım girdilerini kontrol edin.", scope="Katalog kesiti."),
    _card("design_blade", "design", "Kanat planı / 3B ve katlanma teması",
          "İstenen katlanma pozunda kanat yüzeyi; tanımlı yüzeyler temas ederse son temassız açıda ve temas noktasıyla.",
          _design_blade, needs=("active",), missing="Tasarım girdilerini kontrol edin.", cost="heavy",
          scope="Yeniden oluşturulmuş yüzey, CAD değil; temas taraması özeti Tasarım sekmesindedir. Gösterim taraması; "
                "GEOM-03/04 niteliklendirmesi değildir."),
    _card("design_polar", "design", "Saklanan polar eğrileri", "c_l, c_d ve c_l/c_d – α; her Re/Mach hücresi bir çizgi.",
          _polar, needs=("active", "family"), missing="Yukarıdan saklanan bir polar sürümü seçin.",
          scope="Yalnız saklanan tablo noktaları; ara değer ve ekstrapolasyon çizilmez. Verinin türü yukarıdaki kaynak "
                "satırındadır."),
    _card("design_envelope", "design", "BEM veri kapsam haritası",
          "Devir × giriş hızı noktalarında ilk sorguların (α, Re, Mach) saklanan ızgaraya düşüp düşmediği.",
          _envelope, needs=("active", "family"), missing="Yukarıdan saklanan bir polar sürümü seçin.",
          scope="Yalnız indüksiyonsuz başlangıç sorgusu: indüksiyon iç kesitlerde α’yı düşürür; kapsam içindeki bir "
                "nokta BEM’de yine veri dışına çıkabilir."),
    _card("bem_radial", "bem", "Radyal dağılımlar ve toplamlar", "α, dT/dr ve dQ/dr – yarıçap; itki, tork ve güç.",
          lambda c: gf.bem_overlay_figure([c["row"]]), needs=("row",), missing=_NO_BEM,
          scope="İdeal tam açık BEM; eklem kaybı modellenmedi, deneysel referans uyumu değerlendirilmedi."),
    _card("bem_fields", "bem", "Seçili radyal büyüklük", "Yukarıda seçilen eleman yükü, yük yoğunluğu, α, Re veya Mach.",
          _bem_fields, needs=("row", "field"), missing=_NO_BEM, scope="Son BEM çözümü; tam açık rotor (0°)."),
    _card("bem_radial_link", "bem", "Radyal bağlantı grafiği", "Kanat renk ölçeğiyle aynı şeritlerde itki yoğunluğu.",
          _bem_link, needs=("row",), missing=_NO_BEM, scope="Kesikli çizgi menteşe yarıçapı (açık konum)."),
    _card("bem_blade3d", "bem", "Kanat üzerinde alan (3B durağan)", "Kaydın kanadında şerit başına itki yoğunluğu.",
          _bem_blade3d, needs=("row",), missing=_NO_BEM, cost="heavy",
          scope="Hesaplanan: BEM şeritleri, tam açık rotor (0°). Yeniden oluşturulan: kanat yüzeyi, CAD değil."),
    _card("bem_rotation", "bem", "Dönen pervane oynatması", "Kararlı çözümün çözülen devirle dönüşü; itki, tork ve güç okları.",
          _bem_rotation, needs=("row",), missing=_NO_BEM, cost="heavy",
          scope="Açıklayıcı oynatma: yükler zamanla değişmez (kararlı çözüm); zamana bağlı analiz değildir."),
    _card("bem_slipstream", "bem", "Momentum akım tüpü", "BEM halka hızlarından akım tüpü rekonstrüksiyonu.",
          _slipstream, needs=("row",), missing=_NO_BEM, scope="İmpuls, momentum kuramı; girdap izi çözümü veya CFD değildir."),
    _card("bem_mechanism", "bem", "Mekanizma zaman geçmişi", "Tek rijit dış parçanın açısı ve moment terimleri.",
          lambda c: gf.bem_mechanism_figure(c["mechanism"]), needs=("mechanism",),
          missing="Bu kayıtta hesaplanmış mekanizma yok; Analiz’de mekanizma girdileriyle çalıştırın.",
          scope="İlk stop temasına veya rampanın sonuna kadar; aerodinamik geri besleme ve temas tepkisi yok."),
    _card("bem_overlay", "bem", "İki kayıt bindirmesi", "İki BEM kaydının radyal dağılımları ve toplamları aynı eksenlerde.",
          lambda c: gf.bem_overlay_figure([c["row"], c["other"]]), needs=("row", "other"),
          missing="Bindirme için yukarıdan ikinci bir tamamlanmış BEM kaydı seçin.",
          scope="Eşleşme koşulları (veri sürümü, planform, koşul) Karşılaştırma / kayıtlar’da denetlenir."),
    _card("cycle_timeline", "cycle", "Senkron zaman çizelgesi", "Açı, devir ve bağlantı yükleri olaylarla birlikte.",
          lambda c: fcv.timeline_figure(c["cycle"], 0, blade=c["blade"]), needs=("cycle", "blade"), missing=_NO_CYCLE,
          scope=_CYCLE_SCOPE, cost="heavy"),
    _card("cycle_angle", "cycle", "Yük – katlanma açısı", "Pim ekseni momenti açılma, kapanma ve stopta.",
          lambda c: fcv.angle_figure(c["cycle"], "M_pin", blade=c["blade"]), needs=("cycle", "blade"), missing=_NO_CYCLE,
          scope=_CYCLE_SCOPE),
    _card("cycle_contrib", "cycle", "Katkı ayrışımı", "Pim ekseni momentinin kaynaklara ayrışımı (tüm çevrim).",
          lambda c: fcv.contribution_figure(c["cycle"], "M_pin", 0, blade=c["blade"]), needs=("cycle", "blade"),
          missing=_NO_CYCLE, scope=_CYCLE_SCOPE),
    _card("cycle_elements", "cycle", "Menteşe elemanları", "Pim ekseni momentini taşıyan yay, sönüm, stop ve mandal.",
          lambda c: fcv.element_figure(c["cycle"], 0, blade=c["blade"]), needs=("cycle", "blade"), missing=_NO_CYCLE,
          scope=_CYCLE_SCOPE),
    _card("cycle_energy", "cycle", "Enerji dengesi", "İş, kinetik ve yay/stop enerjisi ile denge artığı.",
          lambda c: fcv.energy_figure(c["cycle"], blade=c["blade"]), needs=("cycle", "blade"), missing=_NO_CYCLE,
          scope=_CYCLE_SCOPE),
    _card("cycle_scene", "cycle", "Konumlanmış 3B durum", "İlk örnekte kanatlar ve bağlantı kuvvet/moment okları.",
          lambda c: fcv.scene_figure(c["cycle"], fcv.spec_from_payload(c["cycle"]["geometry"]), 0),
          needs=("cycle",), missing=_NO_CYCLE, scope=_CYCLE_SCOPE + " Renkler yük değildir.", cost="heavy"),
    _card("cycle_playback", "cycle", "3B oynatma", "Çevrimin 80 karelik açıklayıcı oynatması.",
          lambda c: fcv.playback(c["cycle"], fcv.spec_from_payload(c["cycle"]["geometry"])),
          needs=("cycle",), missing=_NO_CYCLE, scope=_CYCLE_SCOPE + " Açıklayıcı oynatma.", cost="heavy"),
    _card("cycle_compare", "cycle", "Çevrim – çevrim karşılaştırması", "İki çevrimin açısı ve pim ekseni momenti.",
          lambda c: fcv.compare_figure([c["other"], c["cycle"]], "M_pin"), needs=("cycle", "other"),
          missing="Karşılaştırma için yukarıdan ikinci bir kaydedilmiş çevrim seçin.",
          scope="Farklı devir profili, aero model veya mekanizma varsayımı karşılaştırmanın koşuludur."),
    _card("coupled_theta", "coupled", "Katlanma açısı θ", "Kanat başına θ zaman geçmişi, kilit ve stop teması gölgeli.",
          lambda c: cv.time_figure(c["coupled"], (("theta_deg", "θ"),), "Katlanma açısı θ [°]", per_blade=True),
          needs=("coupled",), missing=_NO_COUPLED, scope=_COUPLED_SCOPE),
    _card("coupled_thrust", "coupled", "İtki", "Rotor itkisi zaman geçmişi.",
          lambda c: cv.time_figure(c["coupled"], (("thrust_n", "İtki"),), "İtki [N]"),
          needs=("coupled",), missing=_NO_COUPLED, scope=_COUPLED_SCOPE),
    _card("coupled_hinge", "coupled", "Menteşe momenti", "Dış parçaya aerodinamik ve yay+sönüm+stop momenti.",
          lambda c: cv.time_figure(c["coupled"], (("hinge_aero_torque_nm", "Aerodinamik"),
                                                     ("hinge_law_torque_nm", "Yay+sönüm+stop")),
                                      "Dış parçaya menteşe momenti [N·m]", per_blade=True),
          needs=("coupled",), missing=_NO_COUPLED, scope=_COUPLED_SCOPE + " Stop teması penaltı yasasıdır."),
    _card("coupled_coverage", "coupled", "Polar kapsamı", "Sorgulanan α’nın kabul edilen tablo aralığına göre konumu.",
          lambda c: cv.coverage_figure(c["coupled"], "alpha"), needs=("coupled",), missing=_NO_COUPLED,
          scope="DUST tablo dışı α veya Mach’ta durur."),
    _card("coupled_iterations", "coupled", "Bağlaşım yinelemeleri", "Her pencerede preCICE yineleme sayısı.",
          lambda c: cv.iterations_figure(c["coupled"]), needs=("coupled",), missing=_NO_COUPLED, scope=_COUPLED_SCOPE),
    _card("coupled_radial", "coupled", "Radyal dağılım", "Seçilen penceredeki büyüklük, kanat ve parça başına.",
          _coupled_radial, needs=("coupled", "window", "field"), missing=_NO_COUPLED,
          scope="Yalnız geçerli önekteki pencereler seçilebilir; DUST kaldırma çizgisi elemanları."),
    _card("coupled_blade3d", "coupled", "3B kanatlar ve DUST alanı", "Seçilen pencerede konumlanmış kanatlarda eleman itkisi.",
          _coupled_blade3d, needs=("coupled", "window"), missing=_NO_COUPLED, cost="heavy",
          scope="Renk ölçeği tüm pencerelerde sabit; rotorla birlikte görünüm. Yeniden oluşturulan yüzey, CAD değil."),
    _card("coupled_animation", "coupled", "3B oynatma", "Kabul edilen pencerelerin fiziksel zamanla oynatması, olay düğmeleri.",
          _coupled_animation, needs=("coupled",), missing=_NO_COUPLED, cost="heavy",
          scope=_COUPLED_SCOPE + " Oynatma kaba ağ kullanır."),
    _card("coupled_loads", "coupled", "Bağlantı yükleri", "Kanat 1 mafsalının kuvvet ve momentleri, θ ile birlikte.",
          _coupled_loads, needs=("coupled",), missing=_NO_COUPLED, cost="heavy",
          scope="MBDyn mafsal tepkileri; yalnız saklanmış ve bu kayda ait doğrulanmış ek varsa. Yapısal yeterlilik değildir."),
    _card("coupled_response", "coupled", "Tepki zaman çizelgesi", "θ, itki, tork, menteşe momenti ve devir olaylarla.",
          _response, needs=("coupled",), missing=_NO_COUPLED, scope=_COUPLED_SCOPE),
    _card("coupled_overlay", "coupled", "İki bağlaşık kaydın hizalı karşılaştırması",
          "θ, itki ve menteşe momenti; her kayıt kendi olay anında sıfırlanır.",
          lambda c: gf.coupled_overlay_figure([c["coupled"], c["other"]], c["event"]), needs=("coupled", "other", "event"),
          missing="Hizalı karşılaştırma için yukarıdan ikinci bir dinamik kayıt seçin.",
          scope="Yalnız geçerli önek çizilir; kayıtların koşul farkları kendi teknik ayrıntılarındadır."),
    _card("coupled_flow_plane", "coupled", "Hız düzlemi (y = 0)", "dust_post eksenel indüklenmiş hızı, ilk temas penceresi.",
          _flow_plane, needs=("coupled",), missing=_NO_COUPLED, cost="heavy",
          scope="DUST girdap modelinden hesaplanan hız; CFD değildir. Yalnız doğrulanmış akış eki varsa."),
    _card("coupled_wake", "coupled", "Yakın iz şiddeti", "Yarıçapa göre Σ|α|, ilk pencereyle karşılaştırmalı.",
          _wake, needs=("coupled",), missing=_NO_COUPLED, cost="heavy", scope="Yalnız doğrulanmış akış eki varsa."),
    _card("coupled_flow_scene", "coupled", "Akış sahnesi (3B)", "Kanatlar, girdap parçacıkları, panel izi ve hız düzlemi.",
          _flow_scene, needs=("coupled",), missing=_NO_COUPLED, cost="heavy",
          scope="DUST girdap modeli, ilk temas penceresi; CFD değildir. Yalnız doğrulanmış akış eki varsa."),
    _card("archive_file", "archive", "Arşiv dosyası", "Seçilen dosya: şeması bilinen JSON grafik, görüntü veya metin; "
          "diğer JSON’lar tablo/ağaç olarak.", _archive_build, needs=("file",), missing="reports/ altında dosya yok.",
          scope="Arşivlenmiş dosya olduğu gibi okunur; oturum sonuçları bu dosyaların yerine geçmez.", evidence=ARCHIVE),
    _card("legacy_sweep", "legacy", "Gaz kelebeği taraması ve karar puanları",
          "Varyantlara göre θ, itki, efektif çap, itki farkı ve uçuş/kalkış puanları.",
          lambda c: {"images": gf.legacy_pngs("sweep", c["root"])}, cost="heavy", evidence=LEGACY,
          scope="Eski pyfoldable.models V01 ve sentetik APC fikstürü; araştırma tasarımına uygulanmaz."),
    _card("legacy_visuals", "legacy", "Şema, panel ve konsept görselleri",
          "Tek durum şeması, tarama/varyant panelleri, konsept genel bakış ve açılma dizisi.",
          lambda c: {"images": gf.legacy_pngs("visuals", c["root"])}, cost="heavy", evidence=LEGACY,
          scope="Eski V01 CSV zinciri; 2B şema, CAD veya çözüm değildir."),
    _card("legacy_spinup", "legacy", "Dinamik spin-up özeti", "Devir, θ, itki ve efektif çap (basamak/rampa).",
          lambda c: {"images": gf.legacy_pngs("spinup", c["root"])}, cost="heavy", evidence=LEGACY,
          scope="Eski yarı-statik menteşe modeli (θ moment dengesini izler), V01 yapılandırması."),
    _card("legacy_physics", "legacy", "Sabit devirli fizik hata ayıklama seti",
          "Menteşe kinematiği, momentler, itki ayrışımı, efektif çap ve faz portresi.",
          lambda c: {"images": gf.legacy_pngs("physics", c["root"])}, cost="heavy", evidence=LEGACY,
          scope="Eski V02 fikstürü, 7100 RPM sabit ve rampa.", warning=_V02),
]


# ----------------------------------------------------------------------------------------------------- sources
def _design_source(root, active, repository):
    if active is None:
        return {}
    profile = active.inputs.profile
    candidates = rui._families(repository, profile, active.coordinate_sha256)
    selected = st.session_state.get("_research_selected_versions", {}).get(profile)

    def show(k):
        if k is None:
            return "Sürüm seçilmedi"
        return str(k) if k not in candidates else f"{candidates[k].stored_version.version_label} · {k[:8]}"
    chosen = rui._choice(st.selectbox, "Polar sürümü", (None, *candidates), key=f"gallery_design_version_{profile}",
                         default=selected if selected in candidates else None, display=show)
    family = candidates.get(chosen)
    if family is not None:                     # the same source lines and test-fixture warning as Analysis
        st.caption(f"Kaynak: {rui._source_summary(family)}")
        if (note := rui._source_note(family)) is not None:
            st.caption(note)
        if family.evidence_class == "inert_fixture":
            st.warning("Test kaydı: katsayılar mühendislik sonucu olarak kullanılamaz.")
    return {"active": active, "family": family, "repository": repository,
            "keys": {"active": active.identity, "family": chosen},
            "labels": {"active": f"güncel tasarım {profile} · kimlik {active.identity[:8]}",
                       "family": f"polar sürümü {show(chosen)}"}}


def _pick(label, records, key, default, name, *, optional=False):
    options = ((None,) if optional else ()) + tuple(records)

    def show(k):
        if k is None:
            return "Seçilmedi"
        return name(records[k]) if k in records else str(k)  # Streamlit 1.40 AppTest passes the formatted label back
    return rui._choice(st.selectbox, label, options, key=key, default=default if default in options else options[0],
                       display=show)


def _bem_source(root, active, repository):
    records = {k: row for k, (row, _) in rui._retained().items()}
    current = st.session_state.get(rui._ACTIVE)
    default = None
    if current is not None:
        row = json.loads(current[1])
        records.setdefault(row["result_sha256"], row)
        default = row["result_sha256"]
    if not records:
        return {}
    key = _pick("BEM kaydı", records, "gallery_bem_source", default, gf.bem_name)
    row = records[key]
    others = {k: r for k, r in records.items() if k != key and r["aerodynamics"] and r["aerodynamics"]["status"] == "success"}
    other = _pick("İkinci BEM kaydı (bindirme)", others, "gallery_bem_other", None, gf.bem_name, optional=True)
    fields = tuple(k for k in rui._RADIAL_COLUMNS if k not in ("element", "radius_m"))
    field = rui._choice(st.selectbox, "Radyal büyüklük", fields, key="gallery_bem_field", default="thrust_n",
                        display=lambda k: rui._RADIAL_COLUMNS[k][0] if k in rui._RADIAL_COLUMNS else str(k))
    return {"row": row, "other": others.get(other), "mechanism": row if row["mechanism"]["status"] == "computed" else None,
            "field": field, "keys": {"row": key, "other": other, "mechanism": key, "field": field},
            "labels": {"row": "kayıt " + gf.bem_name(row), "other": "ikinci kayıt " + (gf.bem_name(others[other]) if other in others else ""),
                       "mechanism": "kayıt " + gf.bem_name(row) + " · mekanizma", "field": rui._RADIAL_COLUMNS[field][0]}}


def _cycle_source(root, active, repository):
    from . import fold_cycle_ui as fcu
    items = {s["sha"]: s for s in fcu.saved()}
    if not items:
        return {}
    current = fcu.active_row()

    def name(s):
        return f"{s['profile']} · {fcu.PRESETS.get(s['preset'], s['preset'])} · {s['rpm']:.0f} RPM · {s['sha'][:8]}"
    key = _pick("Çevrim kaydı", items, "gallery_cycle_source", current and current["result_sha256"], name)
    others = {k: s for k, s in items.items() if k != key}
    other = _pick("İkinci çevrim (karşılaştırma)", others, "gallery_cycle_other", None, name, optional=True)
    try:
        row = fcu._read(items[key]["path"])
        other_row = fcu._read(others[other]["path"]) if other in others else None
    except (OSError, ValueError, KeyError, TypeError):          # removed or changed after it was listed
        st.warning("Seçilen çevrim kaydı doğrulanamadı (dosya silinmiş veya değişmiş olabilir).")
        return {}
    blade = 0                                  # identical blades are stored once (no in-plane gravity)
    if "events_by_blade" in row:
        blade = rui._choice(st.radio, "Kanat", tuple(range(row["case"]["blade_count"])), key="gallery_cycle_blade",
                            default=0, horizontal=True, display=lambda b: f"Kanat {b + 1}")
    return {"cycle": row, "other": other_row, "blade": blade, "keys": {"cycle": key, "other": other, "blade": blade},
            "labels": {"cycle": "çevrim " + name(items[key]), "other": "ikinci çevrim " + (name(others[other]) if other_row else ""),
                       "blade": f"kanat {blade + 1}"}}


def _coupled_source(root, active, repository):
    from . import coupled_ui
    records = {k: row for k, (row, _) in coupled_ui.retained().items()}
    if not records:
        return {}
    current = coupled_ui.active_result()

    def name(row):
        i = row["request"]["research"]["inputs"]
        return f"{i['profile']} · {i['rpm']:.0f} RPM · {i['inflow_m_s']:g} m/s · {row['result_sha256'][:8]}"
    key = _pick("Dinamik kayıt", records, "gallery_coupled_source", current and current["result_sha256"], name)
    others = {k: r for k, r in records.items() if k != key}
    other = _pick("İkinci dinamik kayıt (hizalı karşılaştırma)", others, "gallery_coupled_other", None, name, optional=True)
    labels = cv.EVENT_LABELS
    event = rui._choice(st.radio, "Hizalama olayı", ("release", "first_contact"), key="gallery_coupled_event",
                        default="release", horizontal=True, display=lambda k: labels.get(k, str(k)))
    from pyfoldable.coupled import flow
    row = records[key]
    valid = tuple(r["window"] for r in row["series"][:row["execution"]["valid_prefix_windows"]])
    contact = flow.events(row).get("first_contact")
    window = rui._choice(st.selectbox, "Pencere (radyal ve 3B kartlar; geçerli önek)", valid, key="gallery_coupled_window",
                         default=contact if contact in valid else valid[-1]) if valid else None
    field = rui._choice(st.radio, "Radyal büyüklük", tuple(coupled_ui._RADIAL_LABELS), key="gallery_coupled_field",
                        default="alpha_deg", horizontal=True,
                        display=lambda k: coupled_ui._RADIAL_LABELS.get(k, str(k)).split(" [")[0])
    return {"coupled": row, "other": others.get(other), "event": event, "root": root, "window": window, "field": field,
            "keys": {"coupled": key, "other": other, "event": event, "window": window, "field": field},
            "labels": {"coupled": "kayıt " + name(row), "other": "ikinci kayıt " + (name(others[other]) if other in others else ""),
                       "event": "hizalama: " + labels[event], "window": f"pencere {window}",
                       "field": coupled_ui._RADIAL_LABELS[field]}}


def _archive_source(root, active, repository):
    files = archive_files(root)
    folders = (".", *sorted({f.split("/")[0] for f in files if "/" in f}))
    folder = rui._choice(st.selectbox, "Klasör (reports/)", folders, key="gallery_archive_folder", default=".")
    inside = tuple(f for f in files if (f.split("/")[0] == folder if folder != "." else "/" not in f))
    if not inside:
        return {}
    name = rui._choice(st.selectbox, "Dosya", inside, key="gallery_archive_file", default=inside[0])
    path = archive_path(root, name)
    image = path.suffix.lower() in _IMAGES and "demo" in name
    return {"file": path, "evidence": SCREENSHOT if image else ARCHIVE,
            "keys": {"file": (name, path.stat().st_mtime_ns)}, "labels": {"file": f"reports/{name}"}}


_SOURCES = {"design": _design_source, "bem": _bem_source, "cycle": _cycle_source, "coupled": _coupled_source,
            "archive": _archive_source, "legacy": lambda root, active, repository: {"root": root}}


# ---------------------------------------------------------------------------------------------------- renderer
def _show(result, card_id):
    if isinstance(result, tuple):
        st.warning("Görsel üretilemedi: " + result[1])
    elif not isinstance(result, dict):
        rui._plot(result, f"gallery_plot_{card_id}")
    else:
        for name, data in result.get("images", ()):
            st.image(data, caption=name)
        if "readme" in result:
            with st.expander("Klasörün README metni"):
                st.markdown(result["readme"])
        if "markdown" in result:
            st.markdown(result["markdown"])
        if "text" in result:
            st.text(result["text"])
        if "json" in result:
            st.caption("Şeması bilinmeyen dosya: grafik yerine içerik ağacı gösterilir.")
            st.json(result["json"], expanded=False)


def _render_card(card, ctx, build_light):
    st.markdown(f"**{card['title']}**")
    st.caption("Ne gösterir: " + card["explains"])
    if card["warning"]:
        st.warning(card["warning"])
    if any(ctx.get(n) is None for n in card["needs"]):
        st.info("Kaynak yok: " + card["missing"])
        return
    labels = ctx.get("labels", {})
    source = " + ".join(labels[n] for n in card["needs"]) or _LEGACY_SOURCE
    st.caption(f"Veri kaynağı: {source} · {ctx.get('evidence', card['evidence'])}")
    st.caption(card["scope"])
    cache = st.session_state.setdefault(_CACHE, {})
    key = (card["id"], *(ctx["keys"][n] for n in card["needs"]))
    label = "Üret" if card["cost"] == "light" else "Üret (ağır, birkaç saniye)"
    if st.button(label, key=f"gallery_build_{card['id']}") or (build_light and card["cost"] == "light"):
        cache.pop(key, None)
        try:
            result = card["build"](ctx)
        except Exception as exc:  # noqa: BLE001 - a card isolates its builder: the failure stays visible, the page works
            result = ("error", str(exc) or type(exc).__name__)
        cache[key] = result
        while len(cache) > _CACHE_MAX:
            cache.pop(next(iter(cache)))
    if key in cache:
        _show(cache[key], card["id"])


def render_gallery(root: Path, active, repository):
    st.subheader("Görseller")
    st.caption("Tasarım, sonuç, arşiv ve eski örnek görselleri tek yerde. Sayfa açılınca hiçbir görsel üretilmez; kartlar "
               "kendi düğmesiyle üretilir ve kaynakları değişince yeniden üretilmeleri gerekir. Hiçbir görsel fiziksel "
               "yeterlilik göstermez.")
    name = rui._choice(st.radio, "Bölüm", SECTIONS, key="gallery_section", default=SECTIONS[0], horizontal=True)
    sid = _IDS[name]
    ctx = _SOURCES[sid](root, active, repository)
    build_light = st.button("Hafif görselleri üret", key=f"gallery_light_{sid}",
                            help="Kaynağı olan hafif kartları üretir; ağır kartlar yalnız kendi düğmesiyle üretilir.")
    for card in CARDS:
        if card["section"] == sid:
            with st.container(border=True):
                _render_card(card, ctx, build_light)
