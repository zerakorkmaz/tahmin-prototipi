# Montaj Çevrim Süresi Tahmin Demosu – Proje Kuralları

## Bağlam
- Üniversite bitirme projesi.
- Plastik akışkan parçaları (ör. washer tank / cam suyu deposu) üreten bir
  otomotiv yan sanayi firmasında montaj hatlarının standart süreleri çalışılıyor.
- Firmaya "bunu mu istiyorsunuz?" diye gösterilecek bir tahmin modeli **demosu**.
- Ölçülmüş veri **yok**. Her şey literatür ve makul varsayımlarla üretilir
  (sentetik veri).

## Kurallar
1. Firma, müşteri ya da gerçek parça numarası kullanılmaz.
2. Derin öğrenme yok, yalnızca regresyon. Python (pandas, statsmodels, openpyxl).
3. Türkçe ve sade yazılır.
4. Kaynağı gerçekten okunmamış bir değer kaynaklı gibi yazılmaz.
   Bulunamayan değerler **"VARSAYIM"** olarak işaretlenir ve gerekçesi yazılır.
5. Demo modu: ara adımlarda onay beklenmez; sonda kısa özet verilir.

## Akış (tek script: `src/demo.py`)
1. Parametre tablosu → `data/parametreler.xlsx`
   (parametre | min | tipik | max | birim | kaynak/VARSAYIM)
2. Sentetik veri → `outputs/veri_seti.xlsx`
   çevrim süresi = iş içeriği / operatör sayısı × (1 + denge kaybı) + normal gürültü,
   operatör sayısı 1–4, sabit random seed.
   Öncelik + bağlı iş kısıtı: işler sabit sırada (seri zincir), bağlı işler tek blok
   ve farklı operatörlere bölünemez. Hat her ürün için optimum dengelenir (DP);
   çevrim = en yüklü istasyon, denge kaybı varsayılmaz, hesaplanır.
3. İleri (forward stepwise) regresyon; operatör için hem n hem 1/n aday
   → `outputs/rapor.md` (başta: "Bu sonuçlar sentetik veriye dayanan bir demodur"),
   `outputs/model.json`.
4. Arayüz → `outputs/index.html` (tek dosya, sunucusuz, internetsiz, mobil uyumlu;
   model.json gömülü). Script sonunda Python ve HTML tahminleri karşılaştırılır.
5. Senaryo analizi yapılmaz (operatör sayısı arayüzde değiştirilir).
