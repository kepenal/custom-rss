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

### 1. Portainer ile Dağıtım (Tavsiye Edilen)

1. Portainer panelinizde **Stacks -> Add Stack** bölümüne gidin.
2. **Repository** seçeneğini seçin:
   - **Repository URL:** `git@github.com:kepenal/custom-rss.git` (veya HTTPS adresi)
   - **Repository reference:** `refs/heads/main`
   - **Compose path:** `docker-compose.yml`
3. **Deploy the stack** butonuna tıklayın (Fiziksel `.env` dosyasına gerek yoktur, tüm değişkenler compose içinde tanımlıdır).
4. İsteğe bağlı olarak admin şifresini Portainer arayüzündeki *Environment variables* alanından değiştirebilirsiniz (`DJANGO_SUPERUSER_PASSWORD`).

### 2. Docker Compose CLI İle

```bash
git clone git@github.com:kepenal/custom-rss.git
cd custom-rss

# Production modunda başlatma:
docker compose up -d --build

# Development (Canlı kod geliştirme & debug):
docker compose -f docker-compose.dev.yml up --build
```

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

## API Anahtarı Oluşturma (Django Admin)

API anahtarları `.env` içine yazılmaz, veritabanında SHA-256 hash ile güvenle saklanır:

1. `http://<sunucu-ip-veya-domain>:8000/admin/` adresine gidin.
2. `admin` kullanıcısı ile giriş yapın.
3. **API Anahtarları -> Ekle** butonuna tıklayın.
4. Bir isim verin (örn: `n8n Entegrasyonu` veya `FreeRSS Okuyucum`) ve **Yetki Türü**nü seçin:
   - **Yazma Yetkisi (`write`):** n8n akışlarından `POST /api/flows` ucuna video basmak için.
   - **Okuma Yetkisi (`read`):** FreeRSS vb. istemcilerden `GET /youtube/<channel_slug>` akışını okumak için.
5. **Kaydet** dediğinizde sistem size tek seferlik gösterilecek anahtarı (`crss_write_...` veya `crss_read_...`) ve hazır bağlantı şablonunu verecektir.

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
https://crss.armaganuzun.com/youtube/baris-ozcan?key=<READ_KEY>
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
