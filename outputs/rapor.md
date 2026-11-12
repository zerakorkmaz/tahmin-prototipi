> **Bu sonuçlar sentetik veriye dayanan bir demodur.** Ölçülmüş veri kullanılmamıştır; element süreleri literatürden ve VARSAYIM'lardan alınmıştır (bkz. `data/parametreler.xlsx`).

# Çevrim Süresi Tahmin Modeli – Demo Raporu

## Veri

- 240 satır sentetik ürün varyantı (her operatör sayısı 1–4 için 60 satır), random seed = 42.
- Satır sayısı gerekçesi: 16 aday terim var. Yaygın kural olan 'aday değişken başına en az 10–15 gözlem' ile 160–240 satır gerekir; üst sınır seçildi ve operatör seviyeleri dengeli tutuldu.
- Üretim formülü: `çevrim = iş_içeriği / n × (1 + denge_kaybı) + N(0, 3.0²)`; n=1 iken denge kaybı 0, n≥2 iken %10–20.

## Aday değişkenler

Ürün değişkenleri (hacim, kaynak uzunluğu, vida, klips, hortum, pompa, sensör), operatör için **n** ve **1/n**, ayrıca her ürün değişkeninin **n'e bölünmüş** hali (çünkü üretim formülünde iş içeriği operatör sayısına bölünüyor).

## İleri seçim adımları

Her adımda p-değeri en küçük aday eklenir; p < 0.05 ve düzeltilmiş R² artmıyorsa durulur.

| Adım | Eklenen terim | p | R² | Düz. R² |
|---|---|---|---|---|
| 1 | 1/operator | 1.67e-121 | 0.9010 | 0.9006 |
| 2 | vida/operator | 3.24e-42 | 0.9548 | 0.9544 |
| 3 | hortum/operator | 1.96e-27 | 0.9726 | 0.9722 |
| 4 | klips/operator | 2.85e-19 | 0.9805 | 0.9802 |
| 5 | operator | 4.24e-14 | 0.9848 | 0.9844 |
| 6 | sensor/operator | 6.41e-15 | 0.9883 | 0.9880 |
| 7 | pompa/operator | 9.17e-18 | 0.9915 | 0.9912 |
| 8 | kaynak_m/operator | 6.36e-13 | 0.9932 | 0.9929 |
| 9 | hacim_l/operator | 1.08e-10 | 0.9943 | 0.9941 |
| 10 | vida | 9.73e-03 | 0.9945 | 0.9942 |
| 11 | hortum | 1.81e-02 | 0.9946 | 0.9944 |
| 12 | (durdu: en iyi aday klips, p=0.0557) | 5.57e-02 | – | – |

## Son model

- R² = **0.9946**, düzeltilmiş R² = **0.9944**, artık std. sapma = 3.85 sn

| Terim | Katsayı | Std. hata | p |
|---|---|---|---|
| sabit | 41.367 | 3.256 | 2.53e-28 |
| 1/operator | 16.216 | 4.840 | 9.45e-04 |
| vida/operator | 9.487 | 0.487 | 2.16e-50 |
| hortum/operator | 8.968 | 0.743 | 2.93e-26 |
| klips/operator | 3.629 | 0.202 | 1.65e-45 |
| operator | -7.835 | 0.612 | 1.30e-28 |
| sensor/operator | 7.204 | 0.558 | 5.12e-29 |
| pompa/operator | 9.619 | 0.862 | 2.46e-23 |
| kaynak_m/operator | 12.271 | 1.497 | 1.79e-14 |
| hacim_l/operator | 2.566 | 0.374 | 6.08e-11 |
| vida | 0.745 | 0.267 | 5.72e-03 |
| hortum | 1.062 | 0.446 | 1.81e-02 |

**Denklem:** `çevrim_sn = 41.37 + 16.22·1/operator + 9.49·vida/operator + 8.97·hortum/operator + 3.63·klips/operator − 7.83·operator + 7.20·sensor/operator + 9.62·pompa/operator + 12.27·kaynak_m/operator + 2.57·hacim_l/operator + 0.75·vida + 1.06·hortum`

## Kısa yorum

- Operatör etkisi n ile değil **1/n** ile (ve ürün değişkenleri / n ile) yakalanıyor: bu, süreyi operatör sayısına bölen üretim formülüyle uyumlu.
- '/operator' katsayıları ≈ element süresi × (1 + ortalama denge kaybı) olmalı: vida: 9.49 (formülde 9.8 × ~1.15 ≈ 11.27); hortum: 8.97 (formülde 10.0 × ~1.15 ≈ 11.50); klips: 3.63 (formülde 3.5 × ~1.15 ≈ 4.03); sensor: 7.20 (formülde 6.0 × ~1.15 ≈ 6.90); pompa: 9.62 (formülde 8.5 × ~1.15 ≈ 9.78); kaynak_m: 12.27 (formülde 10 × ~1.15 ≈ 11.50); hacim_l: 2.57 (formülde 2.0 × ~1.15 ≈ 2.30). n=1 satırlarında denge kaybı 0 olduğu için katsayılar bu değerin biraz altında kalabilir.
- Doğrusal `operator` ya da bölünmemiş ürün terimleri seçildiyse, bunlar denge kaybının n=1'de 0, n≥2'de ~%15 olmasından doğan doğrusal olmayan farkı düzeltir; tek başına fiziksel anlamları yoktur.
- Sentetik veri, modelin bulması gereken formülden üretildiği için yüksek R² beklenen bir sonuçtur; gerçek ölçümlerle R² daha düşük çıkacaktır.
- Sınırlama: kaynak ve sızdırmazlık testi gerçekte makine süresidir ve operatör sayısıyla kısalmaz; demoda istenen formül gereği tüm iş içeriği n'e bölünmüştür.

## Dosyalar

- `outputs/veri_seti.xlsx` – sentetik veri
- `outputs/model.json` – katsayılar, dönüşümler, girdi aralıkları
- `outputs/index.html` – çevrimdışı tahmin arayüzü
- `src/demo.py` – hepsini yeniden üretir

## Kaynakça

- [S1] Sprovieri, J. (2022). What's New With Hot-Plate Welding. ASSEMBLY Magazine, 13.09.2022. https://www.assemblymag.com/articles/97311-whats-new-with-hot-plate-welding
- [S2] Wikipedia katkıcıları. Hot plate welding (9 Eylül 2025 sürümü). https://en.wikipedia.org/wiki/Hot_plate_welding
- [S3] TWI Ltd. (t.y.). What is vibration welding of thermoplastics? https://www.twi-global.com/technical-knowledge/faqs/faq-what-is-vibration-welding-of-thermoplastics
- [S4] Weber, A. (2021). Vibration Welding Adapts to Shifting Demands. ASSEMBLY Magazine, 08.02.2021. https://www.assemblymag.com/articles/96123-vibration-welding-adapts-to-shifting-demands
- [S5] Telsonic AG (t.y.). Ultrasonic joining technology systems. https://www.telsonic.com/en/ultrasound-technology/ultrasonic-joining-technology-systems
- [S6] Sprovieri, J. (2009). Leak Testing Auto Parts. ASSEMBLY Magazine, 27.03.2009. https://www.assemblymag.com/articles/86667-leak-testing-auto-parts
- [S7] Chang, G., Peterson, W. (2010). Design for Assembly in Manufacturing Engineering Technology Program: Experience and Success. ASEE Annual Conference, AC 2010-2309 (tablolar: BDI Product Design for Assembly Handbook, 1989). https://peer.asee.org/design-for-assembly-in-manufacturing-engineering-technology-program-experience-and-success.pdf
- [S8] HKUST IELM 317 ders notu (t.y.). Design For Manufacturing/Assembly (DFM, DFA, DFMA); Boothroyd & Dewhurst (1991)'e atıfla. https://ieda.ust.hk/dfaculty/ajay/courses/ielm317/lecs/dfm/dfm.pdf
- [S9] Teni, M.H.M., Naroh, A., Maliki, K.A.A., Tukiran, A. (2019). Design Development of a Coffee Maker using Design for Assembly Method. IJEAT 9(2). DOI: 10.35940/ijeat.B4942.129219
- [S10] Guns, B. (t.y.). Design for Manufacturing (DFM). Engineering LibreTexts, Northeast Wisconsin Technical College. https://eng.libretexts.org/Courses/Northeast_Wisconsin_Technical_College/Design_for_Various_Manufacturing_Methods/01:_Design_for_Manufacturing_(DFM)
- [S11] Yin, M., Jiang, W. (2016). The Theory of IE Assembly Line Balance and Optimization. MMEBC 2016, Atlantis Press. https://www.atlantis-press.com/article/25858924.pdf
- [S12] Govender, P., Dewa, M. (2022). Use of Kaizen Principle and Line Balancing Technique for Process Improvement in the Assembly of Automotive Components. South African Journal of Industrial Engineering 33(3), 69–82. DOI: 10.7166/33-3-2790
- [S13] Rajadurai, R. (2026). Line Balancing Calculation: Formula & Worked Example. MetricMech. https://metricmech.com/articles/line-balancing-calculation
- [S14] King Saud Univ. ders notu (t.y.). Predetermined Motion Time Systems – part 2 (MTM). https://faculty.ksu.edu.sa/sites/default/files/7_pmts_ams_may01_17_-_p2.pdf
- [S15] Tesla (t.y.). Model 3 – Topping Up Windshield Washer Fluid. https://service.tesla.com/docs/Public/diy/model3/en_us/GUID-3A80A08E-9DCB-45A4-9796-BCD9153A4A00.html
- [S16] VWmanual.ru (t.y.). Windscreen washer fluid level (Passat B5, bağımsız el kitabı sitesi). https://vwmanual.ru/en/passat/b5/main/checks/uroven-zhidkosti-stekloomyvatelya
