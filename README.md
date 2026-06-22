# PyFoldable

![Tests](https://github.com/Poyqraz/PyFoldable/actions/workflows/tests.yml/badge.svg)

**Uçtan eklemli katlanabilir pervane analiz ve raporlama paketi**

PyFoldable, İHA elektrik tahrikli pervaneler için uçtan mafsallı (tip-hinged) katlanabilir pervane
geometrisinin model tabanlı analizini, karar desteğini ve mühendislik tasarım raporu üretimini
sağlar. Paket; kinematik model, menteşe dinamiği, kalibrasyonlu itki bölünmesi, motor bağlantılı
performans katmanı ve Seviye-1 CFD hazırlık çıktılarını tek bir doğrulanabilir iş akışında birleştirir.

> **Teknik geçmiş:** Bu depo, [PyThrust](https://github.com/Poyqraz/PyThrust) içindeki
> `pythrust/foldable/` modülünün bağımsız paket olarak dışa aktarılmış halidir. Çekirdek PyThrust
> çözücüsü değiştirilmemiştir; işletim noktası eşlemesi için minimal `pythrust.propellers` ve
> `pythrust.propulsion` dilimleri dahil edilmiştir.

## Projenin amacı

Mühendislik tasarımı bağlamında şu sorulara yanıt üretmek:

1. Katlanabilir pervane, **20 cm temel pervane** (`root-only` / `compact root`) itkisine göre ne kadar kazanç sağlar?
2. **Katlanabilir aday** (`foldable pretest`) konfigürasyonu, **sabit 25 cm referans** (`fixed reference`) pervaneye ne kadar yaklaşır?
3. 7100 dev/dak mühendislik kontrol noktasında motor akımı, gücü ve tork marjı kabul edilebilir mi?
4. Tasarım varyantları ve dağıtım senaryoları raporlanabilir, tekrarlanabilir CSV/şekil çıktılarıyla belgelenebilir mi?

Tüm sonuçlar **simülasyon çıktısıdır**; imalat veya görev kararı için deneysel doğrulama ve CFD
analizi gerektirir.

## Terimler (kod etiketi → Türkçe açıklama)

| Kod / CSV etiketi | Türkçe karşılık |
|-------------------|-----------------|
| `root-only`, `compact root`, `root_only_20cm` | **20 cm temel pervane** — katlanmış/kompakt kök baz çizgisi |
| `foldable`, `foldable pretest`, `pretest_70_fixed` | **Katlanabilir aday** — kalibrasyonlu ön-test foldable konfigürasyonu |
| `fixed reference`, `fixed 25cm`, `25 cm reference` | **Sabit 25 cm referans** — tam açık sabit pervane üst sınırı |
| `gain_vs_compact_20cm_root` | 20 cm temel pervaneye göre itki kazancı (%) |
| `loss_vs_25cm_reference` | Sabit 25 cm referansa göre itki açığı (%) |
| `reference_load_postprocess` | Motor denge çözümü referans yüke; foldable aerodinamik yük sonradan işlenir |

Ayrıntılı rapor dili için bkz. `reports/foldable_v2_engineering_design/terminology_tr.md`.

## Kurulum

```bash
git clone https://github.com/Poyqraz/PyFoldable.git
cd PyFoldable
pip install -e ".[dev,plot]"
```

Gereksinimler: Python ≥ 3.10, NumPy, SciPy. Grafik örnekleri için `matplotlib` (`plot` extra).

## Hızlı çalıştırma

```bash
# Tasarım varyantı tarama (V1)
python3 examples/run_foldable_sweep.py

# Mühendislik tasarım raporu üretimi (V2 motor bağlantılı kontrol noktası)
python3 examples/generate_foldable_engineering_report.py

# Seviye-1 CFD hazırlık CSV'leri (CFD çözümü değil)
python3 examples/run_cfd_preparation.py

# Prescribed-RPM V2 fizik tanıları
python3 examples/run_prescribed_rpm_physics.py

# Motor bağlantılı throttle taraması
python3 examples/run_foldable_operating_point.py
```

Testler:

```bash
pytest tests/ -q
```

## Ana çıktı dosyaları

| Yol | Açıklama |
|-----|----------|
| `reports/foldable_v2_engineering_design/foldable_v2_engineering_design_report.md` | Ana İngilizce mühendislik raporu (Markdown) |
| `reports/foldable_v2_engineering_design/report_conclusion_tr.md` | Türkçe sonuç paragrafı |
| `reports/foldable_v2_engineering_design/report_key_results.csv` | 7100 dev/dak özet metrikleri |
| `reports/foldable_v2_engineering_design/model_assumptions_and_limits.md` | Model varsayımları ve sınırları |
| `reports/foldable_v2_engineering_design/figure_index.md` | Şekil envanteri ve kullanım uyarıları |
| `reports/foldable_v2_engineering_design/docx/` | Final Word raporu (teslim dosyası) |
| `reports/foldable_v2_engineering_design/pdf/` | Final PDF çıktısı (teslim dosyası) |
| `reports/foldable_v2_engineering_design/figures/` | Rapora gömülecek nihai şekiller |
| `outputs/foldable/` | Örnek betiklerin ürettiği ara CSV ve şekiller (gitignore; yerelde yeniden üretilir) |
| `configs/foldable/TIP_HINGED_250_V02.json` | V2 referans konfigürasyonu |

Örnek betikler `outputs/` altına dinamik çıktı yazar; teslim paketinde `reports/` ve `docx/` /
`pdf/` klasörleri referans alınır.

## 7100 dev/dak ana sonuçları (model)

Motor bağlantılı katmanda interpolasyonla elde edilen mühendislik kontrol noktası (`CHECKPOINT_RPM` / 7100 dev/dak):

| Metrik (kod) | Değer | Türkçe yorum |
|--------------|-------|--------------|
| `root_only_20cm_thrust_7100` | **3.73 N** | 20 cm temel pervane itkisi |
| `foldable_pretest_thrust_7100` | **6.37 N** | Katlanabilir aday (kalibrasyonlu ön-test) |
| `fixed_25cm_reference_thrust_7100` | **9.10 N** | Sabit 25 cm referans itkisi |
| `gain_vs_compact_20cm_root` | **+70.9%** | 20 cm temele göre kazanç |
| `loss_vs_25cm_reference` | **−30.0%** | Sabit 25 cm referansa göre açık |
| `interpolated_throttle_7100` | **0.768** | 7100 dev/dak için gereken gaz |
| `motor_current_7100` | **17.0 A** | Batarya akımı (model) |
| `motor_power_7100` | **150 W** | Elektrik gücü (model) |

Kaynak: `reports/foldable_v2_engineering_design/report_key_results.csv`

## Model sınırları

Bu paket **mühendislik ön-tasarım ve raporlama** içindir. Aşağıdaki sınırlar bilinçli olarak
korunmuştur:

| Konu | Durum |
|------|--------|
| **CFD** | Yapılmadı. Seviye-1 hazırlık CSV'leri yalnızca sınır koşulu / işletim noktası girdisi üretir. |
| **Deneysel doğrulama** | Yok. İtki standı, RPM telemetrisi veya dağıtım videosu metrologisi modele dahil değildir. |
| **Motor bağlantısı** | `reference_load_postprocess` seviyesinde: RPM/akım/güç PyThrust referans pervane dengesinden gelir; foldable `D_aero` yükü sonradan işlenir, çözücüye geri beslenmez. |
| **Yapısal analiz** | Menteşe, kilit ve kök bağlantısı gerilme/ömür analizi yoktur. |
| **BEM / kanat çözünürlüğü** | Veritabanı ölçekli itki modeli; kanat profili çözünürlüklü BEM veya CFD yoktur. |

Ayrıntı: `reports/foldable_v2_engineering_design/model_assumptions_and_limits.md`

## Kapsam özeti

- **V1:** Kinematik, efektif çap, tasarım taraması, karar matrisi, görselleştirme
- **V2:** Menteşe dinamiği, itki bölünmesi, motor bağlantılı performans, mühendislik raporu
- **Dahil değil:** PyThrust çekirdek değişiklikleri, OpenMDAO, tam pervane veritabanı, CFD çözücü çalıştırması

## Lisans

Apache-2.0 — bkz. `LICENSE`.
