# Terim Sözlüğü — Mühendislik Tasarım Raporu

Kod ve CSV alan adlarındaki İngilizce teknik etiketlerin rapor dilindeki Türkçe karşılıkları.
Fizik formülleri, CSV sayısal değerleri ve test beklentileri değiştirilmez.

## Temel karşılaştırma pervaneleri

| Kod etiketi | Türkçe ad | Açıklama |
|-------------|-----------|----------|
| `root-only` | 20 cm temel pervane | Yalnızca kök segment; 20 cm efektif çap baz çizgisi |
| `compact root`, `compact_root_20cm` | 20 cm temel pervane | Dış raporlama bazı; `gain_vs_compact_20cm_root` bu çizgiye göredir |
| `foldable`, `foldable pretest` | Katlanabilir aday | Dağıtılmış uç segmentli V2 konfigürasyonu; kalibrasyonlu ön-test itki |
| `fixed reference`, `fixed 25cm` | Sabit 25 cm referans pervane | Tam açık, katlanmayan 25 cm pervane üst performans referansı |

## Performans metrikleri

| Kod etiketi | Türkçe açıklama |
|-------------|-----------------|
| `gain`, `gain_vs_compact_20cm_root` | İtki kazancı — 20 cm temel pervaneye göre (%) |
| `loss`, `loss_vs_25cm_reference` | İtki açığı — sabit 25 cm referans pervaneye göre (%) |
| `foldable_pretest_thrust_7100` | 7100 dev/dak’ta katlanabilir aday itkisi (N) |
| `root_only_20cm_thrust_7100` | 7100 dev/dak’ta 20 cm temel pervane itkisi (N) |
| `fixed_25cm_reference_thrust_7100` | 7100 dev/dak’ta sabit 25 cm referans pervane itkisi (N) |

## Motor ve bağlantı

| Kod etiketi | Türkçe açıklama |
|-------------|-----------------|
| `reference_load_postprocess` | Referans pervane yüküyle motor dengesi; katlanabilir aerodinamik yük sonradan işlenir |
| `interpolated_throttle_7100` | 7100 dev/dak’a ulaşmak için gereken gaz (interpolasyon) |
| `motor_torque_margin_foldable` | Katlanabilir aerodinamik torkuna karşı motor tork marjı |

## Teslim klasörleri

| Klasör | Amaç |
|--------|------|
| `docx/` | Final Türkçe Word mühendislik tasarım raporu |
| `pdf/` | Word raporunun PDF çıktısı |
| `figures/` | Rapora gömülecek nihai şekiller |
