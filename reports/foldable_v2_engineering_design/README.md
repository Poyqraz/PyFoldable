# Mühendislik Tasarım Raporu — V2 Paketi

Bu klasör, uçtan eklemli katlanabilir pervane V2 çalışmasının **teslim rapor paketini** içerir.

## Türkçe referans dosyalar (öncelikli)

| Dosya | İçerik |
|-------|--------|
| [`report_conclusion_tr.md`](report_conclusion_tr.md) | Sonuç paragrafı — rapor dili |
| [`report_key_results.csv`](report_key_results.csv) | 7100 dev/dak özet metrikleri |
| [`terminology_tr.md`](terminology_tr.md) | Kod etiketi → Türkçe terim eşlemesi |
| [`docx/`](docx/) | Final Word raporu (teslim) |
| [`pdf/`](pdf/) | Final PDF çıktısı (teslim) |
| [`figures/`](figures/) | Rapora gömülecek nihai şekiller |

**Görsel üretim:** V2 fizik şekilleri (`constant_7100_*.png`) için
`python3 examples/run_prescribed_rpm_physics.py` çalıştırın; çıktılar
`outputs/foldable/dynamics/physics/figures/` altında oluşur. Teslim için bu dosyaları
`figures/` klasörüne kopyalayın (bkz. `figures/README.md`).

## 7100 dev/dak özet (model)

| Karşılaştırma | Değer |
|---------------|-------|
| 20 cm temel pervane | 3.73 N |
| Katlanabilir aday | 6.37 N |
| Sabit 25 cm referans pervane | 9.10 N |
| İtki kazancı (20 cm temele göre) | +%70.9 |
| İtki açığı (sabit 25 cm referansa göre) | %30.0 |

## İngilizce teknik ekler

| Dosya | İçerik |
|-------|--------|
| [`foldable_v2_engineering_design_report.md`](foldable_v2_engineering_design_report.md) | Tam mühendislik raporu |
| [`model_assumptions_and_limits.md`](model_assumptions_and_limits.md) | Model varsayımları ve geçerlilik kapsamı |
| [`figure_index.md`](figure_index.md) | Şekil envanteri |

Yeniden üretim: `python3 examples/run_deployment_diagnostics.py` ardından
`python3 examples/generate_foldable_engineering_report.py`
