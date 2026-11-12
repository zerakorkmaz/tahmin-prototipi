> **Bu sonuçlar sentetik veriye dayanan bir demodur.** Ölçülmüş veri kullanılmamıştır; element süreleri literatürden ve VARSAYIM'lardan alınmıştır (bkz. `data/parametreler.xlsx`).

# Çevrim Süresi Tahmin Modeli – Demo Raporu

## Veri

- 240 satır sentetik ürün varyantı (her operatör sayısı 1–4 için 60 satır), random seed = 42.
- Satır sayısı gerekçesi: 16 aday terim var. Yaygın kural olan 'aday değişken başına en az 10–15 gözlem' ile 160–240 satır gerekir; üst sınır seçildi ve operatör seviyeleri dengeli tutuldu.
- Üretim formülü: `çevrim = iş_içeriği / n × (1 + denge_kaybı) + N(0, 3.0²)`.
- **Öncelik ve bağlı iş kısıtı:** İşler sabit bir sırayla yapılır (kaynak → pompa+hortum → sensör → hortumlar → braket+vidalar → klipsler → test → kutulama). Bağlı işler (yükleme+kaynak, pompa+kendi hortumu, braket+vidaları, yükleme+test) tek blok sayılır ve **farklı operatörlere bölünemez** [S17], [S18]. Her ürün için bloklar n operatöre sırayı bozmadan, en yüklü istasyonu en aza indirecek şekilde (tam çözüm) dağıtılır. Çevrim süresi en yüklü istasyonun süresidir [S19], bu yüzden **en uzun bağlı işin altına inemez** [S20].
- Bu yüzden denge kaybı artık varsayılmıyor, kısıtlardan **hesaplanıyor**: `denge_kaybı = n × çevrim / iş_içeriği − 1`.

| Operatör | Ort. denge kaybı | Min | Maks | Çevrim / en uzun bağlı iş (ort. – min) |
|---|---|---|---|---|
| 1 | %0.0 | %0.0 | %0.0 | 4.91 – 3.44 |
| 2 | %4.4 | %0.1 | %14.8 | 2.61 – 2.01 |
| 3 | %6.3 | %0.9 | %16.7 | 1.70 – 1.22 |
| 4 | %14.8 | %0.8 | %35.0 | 1.38 – 1.12 |

Literatürde %10–20 denge kaybı 'iyi', %20 üstü 'kötü' sayılıyor [S11]. Operatör sayısı arttıkça kısıtlar yüzünden kaybın büyümesi beklenen bir sonuç. Son sütun 1'e ne kadar yakınsa hat o kadar en uzun bağlı işe (burada hep yükleme+kaynak) dayanmış demektir; 1'e ulaştığında operatör eklemek çevrimi artık kısaltmaz. Bu varsayımlarla 1–4 operatörde bu sınıra henüz değilmiyor, sınır daha fazla operatörde devreye girer.

## Aday değişkenler

Ürün değişkenleri (hacim, kaynak uzunluğu, vida, klips, hortum, pompa, sensör), operatör için **n** ve **1/n**, ayrıca her ürün değişkeninin **n'e bölünmüş** hali (çünkü üretim formülünde iş içeriği operatör sayısına bölünüyor).

## İleri seçim adımları

Her adımda p-değeri en küçük aday eklenir; p < 0.05 ve düzeltilmiş R² artmıyorsa durulur.

| Adım | Eklenen terim | p | R² | Düz. R² |
|---|---|---|---|---|
| 1 | 1/operator | 1.73e-135 | 0.9245 | 0.9241 |
| 2 | vida/operator | 3.20e-42 | 0.9655 | 0.9652 |
| 3 | hortum/operator | 4.39e-30 | 0.9801 | 0.9799 |
| 4 | klips/operator | 1.65e-23 | 0.9870 | 0.9868 |
| 5 | sensor/operator | 9.18e-14 | 0.9898 | 0.9895 |
| 6 | kaynak_m/operator | 1.44e-12 | 0.9917 | 0.9915 |
| 7 | pompa/operator | 3.58e-13 | 0.9934 | 0.9932 |
| 8 | hacim_l/operator | 1.04e-12 | 0.9947 | 0.9945 |
| 9 | vida | 7.15e-04 | 0.9950 | 0.9948 |
| 10 | klips | 2.18e-02 | 0.9951 | 0.9949 |
| 11 | (durdu: en iyi aday pompa, p=0.176) | 1.76e-01 | – | – |

## Son model

- R² = **0.9951**, düzeltilmiş R² = **0.9949**, artık std. sapma = 3.66 sn

| Terim | Katsayı | Std. hata | p |
|---|---|---|---|
| sabit | 12.528 | 1.625 | 3.84e-13 |
| 1/operator | 41.502 | 3.897 | 9.02e-22 |
| vida/operator | 10.884 | 0.465 | 1.33e-62 |
| hortum/operator | 9.829 | 0.352 | 1.41e-75 |
| klips/operator | 4.000 | 0.409 | 4.22e-19 |
| sensor/operator | 6.922 | 0.521 | 3.32e-30 |
| kaynak_m/operator | 12.777 | 1.424 | 1.06e-16 |
| pompa/operator | 7.852 | 0.825 | 2.59e-18 |
| hacim_l/operator | 2.663 | 0.354 | 1.27e-12 |
| vida | -0.899 | 0.260 | 6.49e-04 |
| klips | -0.595 | 0.258 | 2.18e-02 |

**Denklem:** `çevrim_sn = 12.53 + 41.50·1/operator + 10.88·vida/operator + 9.83·hortum/operator + 4.00·klips/operator + 6.92·sensor/operator + 12.78·kaynak_m/operator + 7.85·pompa/operator + 2.66·hacim_l/operator − 0.90·vida − 0.60·klips`

## Kısa yorum

- Operatör etkisi n ile değil **1/n** ile (ve ürün değişkenleri / n ile) yakalanıyor: bu, süreyi operatör sayısına bölen üretim formülüyle uyumlu.
- '/operator' katsayıları ≈ element süresi × (1 + ortalama denge kaybı) olmalı: vida: 10.88 (formülde 9.8 × ~1.06 ≈ 10.42); hortum: 9.83 (formülde 10.0 × ~1.06 ≈ 10.64); klips: 4.00 (formülde 3.5 × ~1.06 ≈ 3.72); sensor: 6.92 (formülde 6.0 × ~1.06 ≈ 6.38); kaynak_m: 12.78 (formülde 10 × ~1.06 ≈ 10.64); pompa: 7.85 (formülde 8.5 × ~1.06 ≈ 9.04); hacim_l: 2.66 (formülde 2.0 × ~1.06 ≈ 2.13). n=1 satırlarında denge kaybı 0 olduğu için katsayılar bu değerin biraz altında kalabilir.
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
- [S17] Triki, H., Hachicha, W., Mellouli, A., Masmoudi, F. (2015). An Assembly Line Balancing Problem Automotive Cables. Management and Production Engineering Review 6(1), 59–66. DOI: 10.1515/mper-2015-0008
- [S18] Hamzadayı, A. (2022). Benders Decomposition Algorithm for Solving the Type-II Simple Assembly Line Balancing Problem with Zoning Restrictions. Yüzüncü Yıl Üniv. Fen Bilimleri Enst. Dergisi 27(2), 400–415. DOI: 10.53433/yyufbed.1080238
- [S19] Sgarbossa, F. (t.y.). Assembly Systems Design and Balancing (ders sunumu, NTNU TPK4191). https://jvatn.folk.ntnu.no/eLearning/TPK4191/slides/Fabio_AS_DesignAndBalancing.pdf
- [S20] King Saud Univ. IE 314 Operations Management II, Lecture 5: Assembly-Line Balancing (t.y.). https://faculty.ksu.edu.sa/sites/default/files/line_balancing.pdf
