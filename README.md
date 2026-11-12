# Custom RSS — YouTube RSS Toplayıcı ve Zenginleştirilmiş Feed Servisi

Bu proje, arayüzü olmayan (headless), Django tabanlı bir arka plan servisidir. **n8n** üzerinden takip edilen YouTube kanallarının video verilerini, LLM ile hazırlanmış **özetlerini** ve **zaman damgalı önemli anlarını (key moments)** kabul eder; FreeRSS vb. RSS okuyucuların doğrudan tüketeceği standart **RSS 2.0 XML** feed'lerine dönüştürür.

---

## Öne Çıkan Özellikler

- **Headless & Hafif:** HTML arayüzü yoktur, yönetim sadece **Django Admin** üzerinden yapılır.
- **Giriş Ucu (`POST /api/flows`):** n8n veya diğer otomasyon araçlarından JSON formatında veri alır. Aynı `video_id` tekrar geldiğinde duplicate oluşturmaz, günceller (idempotent).
- **Çıkış Ucu (`GET /youtube/<channel_slug>`):** Standart RSS 2.0 uyumlu XML feed döner. Açıklamada özet ve tıklanabilir YouTube zaman damgaları (`https://youtu.be/<video_id>?t=seconds`) HTML CDATA olarak yer alır.
- **Slug Normalizasyonu:** Türkçe karakterler (`ş` &rarr; `s`, `ı` &rarr; `i`, `ü` &rarr; `u` vb.) ve boşluklar otomatik olarak düzeltilir.
- **Çift Katmanlı Yetkilendirme (Write vs Read):**
  - **Yazma Anahtarı (`write`):** n8n için ayrı yetki. Sadece veri girmeye izin verir.
  - **Okuma Anahtarı (`read`):** RSS istemcisi için ayrı yetki. RSS okuyucular için `?key=<token>` query parametresi de desteklenir.
  - Anahtarlar veritabanında **SHA-256 hash** ile saklanır.
- **Docker & Compose & Portainer Uyumlu:** Tek komutla PostgreSQL ve Gunicorn konteynerleri kalkar, superuser otomatik açılır.

---

## Kurulum ve Dağıtım

### 1. Docker Compose İle (Tavsiye Edilen)

1. Depoyu klonlayın ve dizine geçin:
   ```bash
   git clone git@github.com:kepenal/custom-rss.git
   cd custom-rss
   ```
2. `.env` dosyasını oluşturun:
   ```bash
   cp .env.example .env
   nano .env  # Parolaları ve SECRET_KEY değerlerini düzenleyin
   ```
3. Servisi başlatın:
   ```bash
   docker compose up -d --build
   ```
4. Servis `http://localhost:8000` üzerinde hazırdır.
   - Django Admin: `http://localhost:8000/admin/` (.env içindeki `DJANGO_SUPERUSER_*` ile)
   - Sağlık Kontrolü: `http://localhost:8000/health/`

### 2. Yerel Geliştirme (Python Sanal Ortam)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py test
python manage.py runserver 0.0.0.0:8000
```

---

## API Kullanım Kılavuzu

### 1. n8n Veri Girişi (`POST /api/flows`)

**Yetkilendirme:**
- HTTP Header: `Authorization: Bearer <WRITE_TOKEN>` veya `X-API-Key: <WRITE_TOKEN>`

**Payload (JSON):**
```json
{
  "channel": "Barış Özcan",
  "channel_url": "https://www.youtube.com/@BarisOzcan",
  "video_id": "dQw4w9WgXcQ",
  "title": "Evrenin Sonu Nasıl Olacak?",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "published_at": "2026-11-12T10:00:00Z",
  "summary": "Kozmolojik modeller ve evrenin olası son senaryoları ele alınıyor.",
  "key_moments": [
    {
      "time": "01:23",
      "seconds": 83,
      "text": "Büyük Donma (Big Freeze) açıklaması"
    },
    {
      "time": "05:40",
      "seconds": 340,
      "text": "Karanlık Enerji etkisi"
    }
  ]
}
```

**CURL Test Örneği:**
```bash
curl -X POST http://localhost:8000/api/flows \
  -H "Authorization: Bearer crss_write_n8n_secret_token_example" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "Barış Özcan",
    "video_id": "dQw4w9WgXcQ",
    "title": "Evrenin Sonu",
    "summary": "Kısa test özeti"
  }'
```

**Yanıt (201 Created veya 200 OK):**
```json
{
  "status": "ok",
  "action": "created",
  "video_id": "dQw4w9WgXcQ",
  "channel": "baris-ozcan",
  "title": "Evrenin Sonu"
}
```

---

### 2. RSS Feed Tüketimi (`GET /youtube/<channel_slug>`)

FreeRSS veya herhangi bir RSS okuyucuda URL alanına:

```
https://rss.yourdomain.com/youtube/baris-ozcan?key=<READ_TOKEN>
```

ya da (eğer istemci başlık destekliyorsa):
```bash
curl -H "Authorization: Bearer <READ_TOKEN>" https://rss.yourdomain.com/youtube/baris-ozcan
```

**XML Feed Örneği:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Barış Özcan - YouTube RSS</title>
    <link>https://www.youtube.com/@BarisOzcan</link>
    <description>Barış Özcan kanalına ait yapay zekâ özetli ve zaman damgalı RSS feed akışı.</description>
    <language>tr</language>
    <item>
      <title>Evrenin Sonu</title>
      <link>https://www.youtube.com/watch?v=dQw4w9WgXcQ</link>
      <guid isPermaLink="false">dQw4w9WgXcQ</guid>
      <pubDate>Thu, 12 Nov 2026 10:00:00 +0000</pubDate>
      <description><![CDATA[
        <h3>Özet</h3>
        <p>Kozmolojik modeller ve evrenin olası son senaryoları ele alınıyor.</p>
        <h3>Önemli Anlar</h3>
        <ul>
          <li><a href="https://youtu.be/dQw4w9WgXcQ?t=83"><strong>[01:23]</strong></a> Büyük Donma (Big Freeze) açıklaması</li>
        </ul>
        <p><a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">YouTube'da İzle &rarr;</a></p>
      ]]></description>
    </item>
  </channel>
</rss>
```

---

## Nginx ve SSL Entegrasyonu

`nginx/custom-rss.conf` dosyası hazır bir sanal sunucu ve ters vekil konfigürasyonudur. `?key=` parametresinin access log dosyasında açık görünmemesi için log maskeleme tanımı (`[REDACTED]`) içerir.

---

## Lisans

MIT
