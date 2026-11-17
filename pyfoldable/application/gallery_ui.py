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
_TEXT = {".md", ".txt", ".csv", ".toml", ".py", ".sh"}
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
    if suffix in _TEXT:
        return {"markdown" if suffix == ".md" else "text": path.read_text(encoding="utf-8", errors="replace")}
    raise ValueError("Bu dosya türü galeride gösterilmez (ikili veri).")


# ------------------------------------------------------------------------------------------------------- cards
def _airfoil(ctx):
    from . import research_views
    active = ctx["active"]
    return research_views.airfoil_figure(next(f for f in active.design.airfoils if f.id == active.inputs.profile))


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
    _card("design_polar", "design", "Saklanan polar eğrileri", "c_l, c_d ve c_l/c_d – α; her Re/Mach hücresi bir çizgi.",
          _polar, needs=("active", "family"), missing="Yukarıdan saklanan bir polar sürümü seçin.",
          scope="Ekli akış XFOIL tablo noktaları; ayrılmış akış ve ekstrapolasyon yok."),
    _card("design_envelope", "design", "BEM veri kapsam haritası",
          "Devir × giriş hızı noktalarında ilk sorguların (α, Re, Mach) saklanan ızgaraya düşüp düşmediği.",
          _envelope, needs=("active", "family"), missing="Yukarıdan saklanan bir polar sürümü seçin.",
          scope="Yalnız indüksiyonsuz başlangıç sorgusu: indüksiyon iç kesitlerde α’yı düşürür; kapsam içindeki bir "
                "nokta BEM’de yine veri dışına çıkabilir. Statik (0 m/s) itki bu verilerle hesaplanamaz."),
    _card("bem_radial", "bem", "Radyal dağılımlar ve toplamlar", "α, dT/dr ve dQ/dr – yarıçap; itki, tork ve güç.",
          lambda c: gf.bem_overlay_figure([c["row"]]), needs=("row",), missing=_NO_BEM,
          scope="İdeal tam açık BEM; eklem kaybı modellenmedi, deneysel referans uyumu değerlendirilmedi."),
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
          lambda c: fcv.timeline_figure(c["cycle"], 0), needs=("cycle",), missing=_NO_CYCLE, scope=_CYCLE_SCOPE,
          cost="heavy"),
    _card("cycle_angle", "cycle", "Yük – katlanma açısı", "Pim ekseni momenti açılma, kapanma ve stopta.",
          lambda c: fcv.angle_figure(c["cycle"], "M_pin"), needs=("cycle",), missing=_NO_CYCLE, scope=_CYCLE_SCOPE),
    _card("cycle_contrib", "cycle", "Katkı ayrışımı", "Pim ekseni momentinin kaynaklara ayrışımı (tüm çevrim).",
          lambda c: fcv.contribution_figure(c["cycle"], "M_pin", 0), needs=("cycle",), missing=_NO_CYCLE,
          scope=_CYCLE_SCOPE),
    _card("cycle_elements", "cycle", "Menteşe elemanları", "Pim ekseni momentini taşıyan yay, sönüm, stop ve mandal.",
          lambda c: fcv.element_figure(c["cycle"], 0), needs=("cycle",), missing=_NO_CYCLE, scope=_CYCLE_SCOPE),
    _card("cycle_energy", "cycle", "Enerji dengesi", "İş, kinetik ve yay/stop enerjisi ile denge artığı.",
          lambda c: fcv.energy_figure(c["cycle"]), needs=("cycle",), missing=_NO_CYCLE, scope=_CYCLE_SCOPE),
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
    return {"row": row, "other": others.get(other), "mechanism": row if row["mechanism"]["status"] == "computed" else None,
            "keys": {"row": key, "other": other, "mechanism": key},
            "labels": {"row": "kayıt " + gf.bem_name(row), "other": "ikinci kayıt " + (gf.bem_name(others[other]) if other in others else ""),
                       "mechanism": "kayıt " + gf.bem_name(row) + " · mekanizma"}}


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
    return {"cycle": row, "other": other_row, "keys": {"cycle": key, "other": other},
            "labels": {"cycle": "çevrim " + name(items[key]), "other": "ikinci çevrim " + (name(others[other]) if other_row else "")}}


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
    return {"coupled": records[key], "other": others.get(other), "event": event, "root": root,
            "keys": {"coupled": key, "other": other, "event": event},
            "labels": {"coupled": "kayıt " + name(records[key]), "other": "ikinci kayıt " + (name(others[other]) if other in others else ""),
                       "event": "hizalama: " + labels[event]}}


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
