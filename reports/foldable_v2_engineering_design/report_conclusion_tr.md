# Mühendislik Tasarım Raporu — Sonuç Paragrafı

Katlanır uç-mafsallı V2 pervane tasarımı, model tabanlı değerlendirmede **20 cm temel pervane**
bazına göre anlamlı bir **itki kazancı** sağlamaktadır. 7100 dev/dak mühendislik kontrol
noktasında **katlanabilir aday** itki yaklaşık **6.37 N**, **20 cm temel pervane** itki
**3.73 N** seviyesindedir; bu da yaklaşık **%70.9 itki kazancı** anlamına gelir. Aynı çalışma
noktasında **sabit 25 cm referans pervane** (**9.10 N**) karşısında katlanabilir aday yaklaşık
**%30.0 itki açığı** ile kalmaktadır; bu durum katlanabilirlik–performans dengesinin beklenen
bir sonucudur.

Tasarım, taşınabilirlik ve depolama zarfı kısıtlı platformlar için avantajlıdır: sabit referans
pervane kadar itki üretemese de, 20 cm temel pervane konfigürasyonuna kıyasla görev itki
seviyesine yaklaşmaktadır. Motor tarafında 7100 dev/dak, gaz interpolasyonu ile erişilebilir
görünmekte; katlanabilir aerodinamik yük `reference_load_postprocess` seviyesinde modellenmekte
(referans pervane dengesi + son-işleme).

**Sonuç olarak:** mevcut bulgular tasarımın fizibilitesini destekler; deneysel doğrulama,
ileri aerodinamik çözüm ve mekanik latch/menteşe dayanım çalışmaları sonraki doğrulama
adımları olarak planlanmalıdır.
