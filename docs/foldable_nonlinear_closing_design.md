# Nonlineer Uç Açılması + Aero Kapanma Momenti — Tasarım Notu

Bu not, uç pal (tip segment) davranışına eklenen iki **opt-in** ve **geriye dönük
uyumlu** fizik eklentisinin gerekçesini, formüllerini, birim analizini ve kabullerini
belgeler. Varsayılanlar mevcut V1/V2 çıktılarını **birebir** korur.

## 1. Motivasyon (literatür)

- Merkezkaç açılma momenti ω²'ye bağlıdır; eşik RPM civarında açılma hızlı/nonlineerdir.
  Depolanan enerji fazlaysa uç pal tam açık konumu aşabilir ve titreşir (overshoot).
  — *UCF, Design and Analysis of a Foldable Propeller Blade.*
- İleri/ters eksenel akış, uç palde açılmayı geri iten bir **kapanma momenti** üretir →
  kısmi açılma ve verim düşüşü. — *US Patent 11667364.*

Bu fazda **1(i)** kapalı-form nonlineer açılma yasası ve **2(ii)** advance-ratio'ya bağlı
kapanma momenti uygulanır. Zaman-domeni overshoot ve whirl flutter bu fazın dışındadır.

## 2. Nonlineer açılma yasası (`nonlinear_saturation`)

Eşik civarı keskin (front-loaded) açılmayı modelleyen kapalı-form:

```
x = (rpm - rpm_threshold) / (rpm_full_open - rpm_threshold)   # [0, 1]
k = kinematics.curve_sharpness
f = x                                  (k ~ 0  -> doğrusala iner)
f = (1 - exp(-k*x)) / (1 - exp(-k))    (k != 0)
theta = theta_min + f * (theta_max - theta_min)
```

- `k = 0` iken `rpm_only` doğrusal doygunluğu (k_open=1) ile birebir aynıdır.
- `k > 0` eşik civarında daha hızlı açılma verir; `[theta_min, theta_max]` clamp edilir.
- Uygulama: `pyfoldable.kinematics.theta_deg_nonlinear_saturation`.

## 3. Aero kapanma momenti (`aero_closing`)

Proxy model — birim analizi `[Pa]·[m²]·[m] = N·m`:

```
q       = 0.5 * rho * V_axial^2                 # eksenel akış dinamik basıncı [Pa]
A_ref   = extension * tip_segment_length_m       # kordsuz uç referans alanı [m^2]
r_cg    = effective_tip_cg_from_hinge_m           # uç CG kolu [m]
M_close = close_moment_gain * q * A_ref * r_cg    # [N·m], pozitif = açılmaya karşı
```

Denge güncellenir:

```
M_open(omega^2) - M_close = M_resist(theta)
```

- `close_moment_gain` boyutsuz kalibrasyon katsayısıdır (mevcut `aero_hinge_moment_gain`
  deseniyle uyumlu).
- Kapalı: `close_moment_gain = 0` **veya** `axial_velocity_m_s = 0` **veya** `rpm <= 0`.
- Advance ratio bağlantısı: `J = V_axial / (n·D)`; model doğrudan `V_axial`'ı (dolayısıyla
  `q`'yu) kullanır, `J` türetilebilir.
- Uygulama: tek kanonik modül `pyfoldable.aero_closing.closing_moment_nm`; hem
  `kinematics.theta_deg_moment_based` hem `dynamics.hinge_moments.compute_hinge_moments`
  aynı fonksiyonu çağırır (tek kaynak).

## 4. Kabuller (explicit assumptions)

- **Kuazi-statik kapalı-form:** `theta_deg_moment_based` içinde `A_ref`, theta'dan bağımsız
  tam-açık uzantı (`extension = tip_segment_length_m`) referansıyla alınır; böylece denge
  kapalı-form (doğrusal) kalır. Theta'ya bağlı geometri yalnızca V2 dinamik yolunda
  (`theta_dependent=True`) kullanılır.
- **Kordsuz alan proxy'si:** Geometride kord bilgisi olmadığından `A_ref = extension · L`
  proxy'si kullanılır; mutlak büyüklük `close_moment_gain` ile kalibre edilir.
- **Hover varsayılanı:** `V_axial = 0` (hover) → kapanma momenti sıfır.

## 5. Geriye dönük uyumluluk

- Yeni alanlar varsayılan kapalı; `TIP_HINGED_250_V01/V02.json` çıktıları ve mevcut test
  paketi değişmez (regresyon testleri: `tests/test_aero_closing.py`).
- Mod dağıtımı exhaustive; tanımsız `kinematics_mode` → `ValueError`.

## 6. İlgili dosyalar

- Config örneği: `configs/foldable/TIP_HINGED_250_V03.json`
- Demo: `examples/run_tip_nonlinear_closing_demo.py`
- Testler: `tests/test_nonlinear_kinematics.py`, `tests/test_aero_closing.py`
- Konvansiyonlar: `docs/foldable_conventions.md`
