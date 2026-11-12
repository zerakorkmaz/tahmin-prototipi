# tahmin-prototipi

Washer tank montaj hattı için çevrim süresi tahmin **demosu** (sentetik veri).

- Çalıştır: `python3 src/demo.py` (pandas, statsmodels, openpyxl; HTML doğrulaması için node + playwright)
- Sade anlatım: `outputs/aciklama.html`
- Arayüz: `outputs/index.html` (tarayıcıda doğrudan açılır, internet gerekmez)
- Rapor: `outputs/rapor.md` · Model: `outputs/model.json` · Parametreler: `data/parametreler.xlsx`

## Genel sürüm (ürün ailesinden bağımsız)

Ürünü "pompa takma" gibi kalemlerle değil, genel işlem tipleriyle tarif eder
(kolay/zor parça, vida, geçme, esnek bağlantı, kontrol, makine süreleri).
Washer tank ve dış dikiz aynası şablonları hazırdır.

- Çalıştır: `python3 src/genel_demo.py`
- Arayüz: `outputs/genel/index.html` · Rapor: `outputs/genel/rapor.md` · Parametreler: `data/genel_parametreler.xlsx`

## Genel sürüm rev2 (zorluk eki)

Zor parça ve vida için "bunlardan kaçı engelli erişimli" sayısı eklenir; model ek süreyi ayrı katsayıyla öğrenir.
Rev1 dosyaları değişmeden durur.

- Çalıştır: `python3 src/genel_demo_rev2.py`
- Arayüz: `outputs/genel_rev2/index_rev2.html` · Rapor: `outputs/genel_rev2/rapor_rev2.md`
- Sade anlatım: `outputs/aciklama_rev2.html` · Parametreler: `data/genel_parametreler_rev2.xlsx`
