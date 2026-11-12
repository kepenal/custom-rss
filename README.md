# Custom RSS — YouTube RSS Toplayıcı ve Zenginleştirilmiş Feed Servisi

Bu proje, arayüzü olmayan (headless), Django tabanlı modern bir arka plan servisidir. **n8n** ve benzeri otomasyon sistemleri üzerinden takip edilen YouTube kanallarının video verilerini, yapay zekâ (LLM) ile üretilmiş **özetlerini** ve **zaman damgalı önemli anlarını (key moments)** kabul eder; FreeRSS vb. tüm standart RSS okuyucuların doğrudan tüketeceği **RSS 2.0 XML** akışlarına dönüştürür.

---

## 🌟 Öne Çıkan Özellikler

- **Headless & Hafif:** Son kullanıcı HTML arayüzü yerine doğrudan API ve RSS XML sunar; yönetim tamamen **Django Admin** üzerinden yürütülür.
- **Giriş Ucu (`POST /api/flows`):** n8n veya diğer otomasyon araçlarından JSON veri kabul eder. Aynı `video_id` tekrar geldiğinde veriyi günceller (idempotent upsert), duplicate oluşturmaz.
- **Çıkış Ucu (`GET /youtube/<channel_slug>`):** Standart RSS 2.0 uyumlu XML feed döner. Video açıklamalarında özet ve tıklanabilir YouTube zaman damgaları (`https://youtu.be/<video_id>?t=seconds`) HTML CDATA olarak yer alır.
- **Otomatik Slug Normalizasyonu:** Türkçe karakterler (`ş` &rarr; `s`, `ı` &rarr; `i`, `ü` &rarr; `u`, `ö` &rarr; `o`, `ğ` &rarr; `g`, `ç` &rarr; `c`) ve boşluklar otomatik normalize edilir.
- **Çift Katmanlı Güvenli Yetkilendirme (Write vs Read):**
  - **Yazma Yetkisi (`write`):** n8n akışları için ayrı anahtar (`crss_write_...`). Yalnızca video eklemeye/güncellemeye izin verir.
  - **Okuma Yetkisi (`read`):** RSS istemcileri için ayrı anahtar (`crss_read_...`). URL query parametresi (`?key=...`) üzerinden güvenle çalışır.
  - Tüm API anahtarları veritabanında **SHA-256 hash** ile saklanır; düz metin olarak tutulmaz.
- **Docker, Portainer & WhiteNoise Uyumlu:** Tek tıkla ayağa kalkar; WhiteNoise sayesinde hiçbir sunucu static dosyası taşımadan admin paneli eksiksiz CSS/JS ile çalışır.

---

## 🚀 Kurulum ve Dağıtım

### 1. Portainer ile Dağıtım (Tavsiye Edilen)

1. Portainer panelinizde **Stacks -> Add Stack** bölümüne gidin.
2. **Repository** seçeneğini seçin:
   - **Repository URL:** `git@github.com:kepenal/custom-rss.git` (veya HTTPS adresi)
   - **Repository reference:** `refs/heads/main`
   - **Compose path:** `docker-compose.yml`
3. **Deploy the stack** butonuna tıklayın (Fiziksel `.env` dosyasına ihtiyaç yoktur, tüm varsayılanlar compose içinde hazırdır).
4. İsteğe bağlı olarak admin şifresini veya domaini Portainer *Environment variables* kutusundan tanımlayabilirsiniz:
   - `DJANGO_SUPERUSER_PASSWORD=guclu_admin_sifreniz`
   - `ALLOWED_HOSTS=crss.armaganuzun.com,localhost,127.0.0.1`
   - `CSRF_TRUSTED_ORIGINS=https://crss.armaganuzun.com`
   - `PORT=7876`

### 2. Docker Compose CLI İle

```bash
git clone git@github.com:kepenal/custom-rss.git
cd custom-rss

# Production:
docker compose up -d --build

# Development (Canlı reload & debug):
docker compose -f docker-compose.dev.yml up --build
```

### 3. Yerel Geliştirme (Python Sanal Ortam)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py test
python manage.py runserver 0.0.0.0:8000
```

---

## 🔑 API Anahtarı Yönetimi (Django Admin)

API anahtarları `.env` dosyasına yazılmaz; dinamik olarak doğrudan Django Admin arayüzünden oluşturulur:

1. `https://crss.armaganuzun.com/admin/` (veya yerelde `http://localhost:8000/admin/`) adresine gidin.
2. `admin` kullanıcısı ile giriş yapın.
3. Sol menüden **API Anahtarları** &rarr; **API Anahtarı Ekle** butonuna tıklayın.
4. **Anahtar Tanımı/İsim** alanına bir etiket verin (örn: `n8n YouTube Akışı` veya `FreeRSS İstemcim`).
5. **Yetki Türü** seçin:
   - **Yazma Yetkisi (write):** `POST /api/flows` ucuna video verisi basmak için.
   - **Okuma Yetkisi (read):** `GET /youtube/<channel-slug>` RSS feed'lerini okumak için.
6. **Kaydet** butonuna basın. Sistem size `crss_write_...` veya `crss_read_...` şeklinde üretilen anahtarı sarı bir uyarı kutusu içinde **tek seferlik** gösterecektir. Bu anahtarı kopyalayıp güvenli bir yere kaydedin.

---

## 📚 Kapsamlı API Kullanım Dokümantasyonu

### Base URL
- **Canlı (Production):** `https://crss.armaganuzun.com`
- **Yerel Geliştirme (Local):** `http://localhost:8000` (veya docker yerel portu `http://127.0.0.1:7876`)

---

### 1. Video Yükleme ve Güncelleme Ucu (`POST /api/flows`)

n8n iş akışları veya harici istemcilerden YouTube video özetlerini ve zaman damgalı anlarını yüklemek için kullanılır.

- **HTTP Metodu:** `POST`
- **Endpoint:** `/api/flows`
- **Yetkilendirme:** `write` yetkisine sahip API anahtarı zorunludur.
- **Header Alternatifleri (Biri Yeterlidir):**
  - `Authorization: Bearer <WRITE_API_KEY>`
  - `X-API-Key: <WRITE_API_KEY>`
- **İçerik Türü (Content-Type):** `application/json`

#### İstek Gövdesi (Payload Parametreleri):

| Alan Adı | Tip | Zorunlu mu? | Açıklama |
|---|---|:---:|---|
| `channel` | string | **Evet** | YouTube kanalının adı (örn: `Evrim Ağacı`). Kanal sistemde yoksa otomatik açılır. |
| `channel_url` | string (URL) | Hayır | YouTube kanalının bağlantısı (örn: `https://www.youtube.com/@evrimagaci`). |
| `video_id` | string | **Evet** | YouTube Video ID'si (örn: `dQw4w9WgXcQ`). Benzersizdir (Unique). |
| `title` | string | **Evet** | Videonun başlığı. |
| `url` | string (URL) | Hayır | Video doğrudan izleme linki. Boş bırakılırsa `https://www.youtube.com/watch?v=<video_id>` olarak otomatik atanır. |
| `published_at` | string (ISO 8601) | Hayır | Videonun yayınlanma zamanı (örn: `2026-11-12T10:00:00Z`). Boşsa sunucu saati verilir. |
| `summary` | string | Hayır | Videonun yapay zekâ veya kullanıcı özeti metni. |
| `key_moments` | array of objects | Hayır | Zaman damgalı önemli anların listesi. |

##### `key_moments` Eleman Yapısı:
```json
{
  "time": "01:23",      // Okuyucuda görünecek zaman etiketi
  "seconds": 83,         // Tıklanabilir YouTube zaman linki için saniye cinsinden karşılık
  "text": "Bölüm başlığı / açıklaması"
}
```

#### Örnek cURL Çağrısı:
```bash
curl -X POST https://crss.armaganuzun.com/api/flows   -H "Authorization: Bearer crss_write_9a8b7c6d5e4f3a2b1c0d"   -H "Content-Type: application/json"   -d '{
    "channel": "Evrim Ağacı",
    "channel_url": "https://www.youtube.com/@evrimagaci",
    "video_id": "dQw4w9WgXcQ",
    "title": "Evrim Teorisi ve Doğal Seçilim",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "published_at": "2026-11-12T10:00:00Z",
    "summary": "Evrim teorisi, doğal seçilim mekanizmaları ve türleşme süreçleri ele alınıyor.",
    "key_moments": [
      {
        "time": "01:23",
        "seconds": 83,
        "text": "Doğal Seçilim Mekanizması"
      },
      {
        "time": "05:40",
        "seconds": 340,
        "text": "Türleşme Örnekleri"
      }
    ]
  }'
```

#### Başarılı Yanıtlar:

- **201 Created (İlk Kez Eklendiğinde):**
```json
{
  "status": "ok",
  "action": "created",
  "video_id": "dQw4w9WgXcQ",
  "channel": "evrim-agaci",
  "title": "Evrim Teorisi ve Doğal Seçilim"
}
```

- **200 OK (Var Olan Video Güncellendiğinde):**
```json
{
  "status": "ok",
  "action": "updated",
  "video_id": "dQw4w9WgXcQ",
  "channel": "evrim-agaci",
  "title": "Evrim Teorisi ve Doğal Seçilim"
}
```

#### n8n HTTP Request Node Ayarları:
1. **Method:** `POST`
2. **URL:** `https://crss.armaganuzun.com/api/flows`
3. **Authentication:** `None` seçip **Send Headers** alanına:
   - `Authorization`: `Bearer crss_write_ANAHTARINIZ`
4. **Send Body:** `True`
5. **Body Content Type:** `JSON`
6. **Specify Body:** `Using JSON` seçerek yukarıdaki JSON nesnesini bağlayın.

---

### 2. RSS Feed XML Akışı (`GET /youtube/<channel_slug>`)

FreeRSS, Feedly, Inoreader, NetNewsWire, Thunderbird veya herhangi bir RSS okuyucunun doğrudan abone olabileceği zenginleştirilmiş standart RSS 2.0 XML akışı döner.

- **HTTP Metodu:** `GET`
- **Endpoint:** `/youtube/<channel_slug>`
- **Yetkilendirme:** `read` yetkisine sahip API anahtarı zorunludur.

#### Kanal Slug Mantığı:
Kanal isimlerindeki Türkçe karakterler ve boşluklar otomatik çevrilir:
- *Evrim Ağacı* &rarr; `evrim-agaci`
- *Murat Şen* &rarr; `murat-sen`
- *Yukarıalınlı Köyü* &rarr; `yukarialinli-koyu`

#### RSS Okuyucular İçin Kullanım (Query Parametresi):
RSS okuyucu uygulamanıza (FreeRSS vb.) feed linki eklerken URL sonuna `?key=...` parametresini ekleyin:

```
https://crss.armaganuzun.com/youtube/evrim-agaci?key=crss_read_SIZIN_ANAHTARINIZ
```

#### cURL İle Test:
```bash
curl -X GET "https://crss.armaganuzun.com/youtube/evrim-agaci?key=crss_read_SIZIN_ANAHTARINIZ"
```

#### Dönen XML Akışı (RSS 2.0 Standart):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Evrim Ağacı - YouTube RSS</title>
    <link>https://www.youtube.com/@evrimagaci</link>
    <description>Evrim Ağacı kanalına ait yapay zekâ özetli ve zaman damgalı RSS feed akışı.</description>
    <language>tr</language>
    <lastBuildDate>Thu, 12 Nov 2026 14:00:00 +0000</lastBuildDate>
    <atom:link href="https://crss.armaganuzun.com/youtube/evrim-agaci" rel="self" type="application/rss+xml"/>
    <item>
      <title>Evrim Teorisi ve Doğal Seçilim</title>
      <link>https://www.youtube.com/watch?v=dQw4w9WgXcQ</link>
      <guid isPermaLink="false">dQw4w9WgXcQ</guid>
      <pubDate>Thu, 12 Nov 2026 10:00:00 +0000</pubDate>
      <description><![CDATA[
        <h3>Özet</h3>
        <p>Evrim teorisi, doğal seçilim mekanizmaları ve türleşme süreçleri ele alınıyor.</p>
        <h3>Önemli Anlar</h3>
        <ul>
          <li><a href="https://youtu.be/dQw4w9WgXcQ?t=83" target="_blank"><strong>[01:23]</strong></a> Doğal Seçilim Mekanizması</li>
          <li><a href="https://youtu.be/dQw4w9WgXcQ?t=340" target="_blank"><strong>[05:40]</strong></a> Türleşme Örnekleri</li>
        </ul>
        <hr/>
        <p><a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ" target="_blank">YouTube'da İzle &rarr;</a></p>
      ]]></description>
    </item>
  </channel>
</rss>
```

---

### 3. Sistem Sağlık Kontrolü (`GET /health/`)

Uptime robotlar, Portainer healthcheck veya izleme servisleri için veritabanı bağlantısını test eder. Yetkilendirme gerektirmez.

- **HTTP Metodu:** `GET`
- **Endpoint:** `/health/` veya `/health`

#### İstek Örneği:
```bash
curl -X GET https://crss.armaganuzun.com/health/
```

#### Başarılı Yanıt (200 OK):
```json
{
  "status": "ok",
  "database": "ok"
}
```

---

## 🛡️ HTTP Durum ve Hata Kodları Rehberi

| Durum Kodu | Açıklama | Neden Oluşur ve Çözüm |
|---|---|---|
| **200 OK** | Başarılı | Video güncellendi, sağlık kontrolü başarılı veya RSS XML akışı döndü. |
| **201 Created** | Kaydedildi | Yeni bir video başarıyla kaydedildi. |
| **400 Bad Request** | Hatalı İstek | JSON formatı geçersiz veya zorunlu alanlar (`channel`, `video_id`, `title`) gönderilmedi. |
| **401 Unauthorized** | Yetkisiz Erişim | API anahtarı girilmedi, anahtar pasif yapılmış veya yetki türü uyuşmuyor (Örn: `POST /api/flows` ucuna `read` anahtarı verilmesi). |
| **404 Not Found** | Kanal Bulunamadı | İstenen kanal slug'ı veritabanında kayıtlı değil veya henüz o kanala ait video yüklenmemiş. |
| **405 Method Not Allowed** | Yanlış Metot | Endpoint'e desteklenmeyen HTTP metoduyla istek atıldı (Örn: `/api/flows` ucuna GET atılması). |
| **500 Server Error** | Sunucu Hatası | Veritabanı bağlantı kesintisi veya beklenmeyen sunucu içi hata. |

---

## 🔒 Nginx ve Güvenlik Yapılandırması

`nginx/custom-rss.conf` dosyası güvenli ters vekil (reverse proxy) konfigürasyonudur:
- `?key=` parametresinin access log dosyasında açık görünmemesi için otomatik maskeleme (`[REDACTED]`) içerir.
- Statik dosyalar WhiteNoise üzerinden doğrudan konteynerden sunulur.
- Port binding `127.0.0.1:7876` ile yerel kilitlidir.

---

## 📄 Lisans

MIT
