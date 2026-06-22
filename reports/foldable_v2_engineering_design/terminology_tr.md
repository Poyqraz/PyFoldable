# Terim Sözlüğü — Mühendislik Tasarım Raporu

Bu dosya, kod ve CSV alan adlarında kullanılan İngilizce teknik etiketlerin rapor dilindeki
Türkçe karşılıklarını sabitler. **Fizik formülleri, CSV sayısal değerleri ve test beklentileri
değiştirilmez**; yalnızca okuyucu için anlam eşlemesi sağlanır.

## Temel karşılaştırma pervaneleri

| Kod etiketi | Türkçe ad | Açıklama |
|-------------|-----------|----------|
| `root-only` | 20 cm temel pervane | Yalnızca kök segment; katlanmış/kompakt 20 cm efektif çap bazı |
| `compact root`, `compact_root_20cm` | 20 cm temel pervane | Aynı baz; dış raporlama için `gain_vs_compact_20cm_root` bu çizgiye göredir |
| `foldable`, `foldable pretest` | Katlanabilir aday | Uç segmenti dağılmış V2 konfigürasyonu; kalibrasyonlu ön-test itki |
| `fixed reference`, `fixed 25cm` | Sabit 25 cm referans | Tam açık, katlanmayan 25 cm pervane üst performans sınırı |

## Performans metrikleri

| Kod etiketi | Türkçe açıklama |
|-------------|-----------------|
| `gain_vs_compact_20cm_root` | 20 cm temel pervaneye göre itki kazancı (%) |
| `loss_vs_25cm_reference` | Sabit 25 cm referansa göre itki açığı (%) |
| `foldable_pretest_thrust_7100` | 7100 dev/dak’ta katlanabilir aday itkisi (N) |
| `root_only_20cm_thrust_7100` | 7100 dev/dak’ta 20 cm temel pervane itkisi (N) |
| `fixed_25cm_reference_thrust_7100` | 7100 dev/dak’ta sabit 25 cm referans itkisi (N) |

## Motor ve bağlantı

| Kod etiketi | Türkçe açıklama |
|-------------|-----------------|
| `reference_load_postprocess` | Referans pervane yüküyle motor dengesi; foldable aerodinamik yük sonradan işlenir |
| `interpolated_throttle_7100` | 7100 dev/dak’a ulaşmak için gereken gaz (interpolasyon) |
| `motor_torque_margin_foldable` | Foldable aerodinamik torkuna karşı motor tork marjı |

## Teslim klasörleri

| Klasör | Amaç |
|--------|------|
| `docx/` | Final Türkçe Word mühendislik tasarım raporu |
| `pdf/` | Word raporunun PDF çıktısı |
| `figures/` | Rapora gömülecek nihai şekiller (kaynak: `outputs/` veya yeniden dışa aktarım) |
