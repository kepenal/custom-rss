# Custom RSS Hub — Çok Kaynaklı, Kategori Bazlı ve Zenginleştirilmiş RSS Servisi

Bu proje; arayüzü olmayan (headless), Django tabanlı modern bir **RSS Hub** servisidir. **n8n** ve diğer otomasyon sistemleri üzerinden takip edilen YouTube videolarını, web makalelerini, haber bültenlerini ve podcast içeriklerini; yapay zekâ (LLM) ile üretilmiş **özetleri** ve **zaman damgalı önemli anları (key moments / highlights)** ile birlikte kabul eder. FreshRSS vb. tüm standart RSS okuyucuların doğrudan tüketeceği **RSS 2.0 XML** akışlarına dönüştürür.

---

## 🌟 Temel Mimari & Öne Çıkan Özellikler

- **Evrensel Kategori / Kanal Hiyerarşisi (`/<category_slug>/<channel_slug>`):**
  - **Kategori (İçerik Türü / Alan):** `youtube`, `videodaldassak`, `makale`, `haber`, `podcast` vb.
  - **Kanal / Kaynak (RSS Channel):** `allahinyo`, `evrim-agaci`, `medium-yazari` vb.
  - Sistem her iki ucu URL'den çözer; URL'deki kategori veya kanal sistemde yoksa **otomatik olarak (`get_or_create`) veritabanında açar**. Kategoriler asla boş kalmaz.
- **Hibrit Çift Yönlü Uç:**
  - `POST /<kategori>/<kanal>`: Veri yükleme (Writer API / Ingest). Gönderilen içerik doğrudan ilgili kategori ve kanala bağlanır.
  - `GET /<kategori>/<kanal>?key=...`: RSS okuyucu (Reader) için standart RSS 2.0 XML akışı sunar.
- **Toplu Kategori Akışları (`GET /category/<kategori-slug>?key=...`):** Bir kategorideki tüm kanalları tek bir birleşik feed olarak sunar.
- **Gelişmiş Favicon / Logo Hiyerarşisi:**
  - FreshRSS'te logosuz akış kalmaması için kanalın kendi `icon_url` değeri varsa o kullanılır;
  - Kanalın özel logosu yoksa bağlı olduğu kategorinin `icon_url` değeri otomatik devralınır.
- **Otomatik Slug Normalizasyonu:** Türkçe karakterler (`ş` &rarr; `s`, `ı` &rarr; `i`, `ü` &rarr; `u`, `ö` &rarr; `o`, `ğ` &rarr; `g`, `ç` &rarr; `c`) ve boşluklar otomatik normalize edilir.
- **Geriye Dönük %100 Uyumluluk:** Eski n8n akışları (`POST /api/flows`) ve eski RSS abonelikleri (`GET /youtube/<slug>`, `GET /channel/<slug>`) kesintisiz çalışmaya devam eder. Kategori belirtilmeyen eski video istekleri otomatik olarak `YouTube` kategorisine atanır.
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
   - **Yazma Yetkisi (write):** `POST /<kategori-slug>/<kanal-slug>` veya `POST /api/flows` üzerinden veri yüklemek için (`crss_write_...`).
   - **Okuma Yetkisi (read):** `GET /<kategori-slug>/<kanal-slug>?key=...` veya `GET /category/<kategori-slug>?key=...` RSS feed'lerini okumak için (`crss_read_...`).
6. **Kaydet** butonuna basın. Sistem size `crss_write_...` veya `crss_read_...` şeklinde üretilen anahtarı sarı bir uyarı kutusu içinde **tek seferlik** gösterecektir. Bu anahtarı kopyalayıp güvenli bir yere kaydedin.

---

## 📚 Kapsamlı API Kullanım Dokümantasyonu

### Base URL
- **Canlı (Production):** `https://crss.armaganuzun.com`
- **Yerel Geliştirme (Local):** `http://localhost:8000` (veya docker yerel portu `http://127.0.0.1:7876`)

---

### 1. Veri Yükleme ve Güncelleme Uçları (Writer / Ingest API)

#### A) Tavsiye Edilen: Slug Bazlı Dinamik Endpoint (`POST /<kategori-slug>/<kanal-slug>`)

Kategori (içerik türü) ve kanal doğrudan URL üzerinden tanımlanır. Sistemde yoksa her ikisi de **otomatik olarak veritabanında oluşturulur** (`get_or_create`). Böylece kategoriler ve kanallar asla boş kalmaz.

- **HTTP Metodu:** `POST`
- **Endpoint:** `/<kategori-slug>/<kanal-slug>`
  - *Örnek:* `POST /videodaldassak/allahinyo`
  - *Örnek:* `POST /youtube/evrim-agaci`
  - *Örnek:* `POST /makale/medium-yazari`
  - *Alternatif Prefixler:* `/api/flows/<kategori-slug>/<kanal-slug>` veya `/api/<kategori-slug>/<kanal-slug>`
- **Yetkilendirme:** `write` yetkisine sahip API anahtarı zorunludur.
  - Header: `Authorization: Bearer crss_write_...` veya `X-API-Key: crss_write_...`
- **İçerik Türü (Content-Type):** `application/json`

##### Örnek Payload (`POST /videodaldassak/allahinyo`):
```json
{
  "item_id": "vid_001",
  "title": "Yapay Zekâ ile Kodlama Rehberi",
  "url": "https://www.youtube.com/watch?v=vid_001",
  "published_at": "2026-11-12T10:00:00Z",
  "summary": "Bu bölümde yapay zekâ araçlarının modern geliştirme süreçlerine entegrasyonu inceleniyor.",
  "key_moments": [
    {"time": "01:15", "seconds": 75, "text": "Giriş ve Mimari"},
    {"time": "04:20", "seconds": 260, "text": "API Entegrasyonu"}
  ]
}
```

##### cURL Çağrısı:
```bash
curl -X POST https://crss.armaganuzun.com/videodaldassak/allahinyo \
  -H "Authorization: Bearer crss_write_SIZIN_ANAHTARINIZ" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "vid_001",
    "title": "Yapay Zekâ ile Kodlama Rehberi",
    "summary": "Bu bölümde yapay zekâ araçlarının modern geliştirme süreçlerine entegrasyonu inceleniyor.",
    "key_moments": [
      {"time": "01:15", "seconds": 75, "text": "Giriş ve Mimari"},
      {"time": "04:20", "seconds": 260, "text": "API Entegrasyonu"}
    ]
  }'
```

#### B) Standart Endpoint (`POST /api/flows`)

Kategori ve kanal bilgisini URL yerine JSON gövdesinde göndermek isterseniz standart endpoint'i kullanabilirsiniz:

```json
{
  "category": "videodaldassak",
  "channel": "allahinyo",
  "item_id": "vid_001",
  "title": "Yapay Zekâ ile Kodlama Rehberi",
  "summary": "AI özet metni...",
  "key_moments": [{"time": "01:15", "seconds": 75, "text": "Giriş"}]
}
```
*(Not: `category` belirtilmezse ve `video_id` gönderilirse otomatik olarak `YouTube` kategorisi atanır; diğer durumlarda `Genel` kategorisine bağlanır.)*

#### Payload Parametreleri Tablosu:

| Alan Adı | Tip | Zorunlu mu? | Açıklama |
|---|---|:---:|---|
| `item_id` (veya `video_id`) | string | **Evet** | İçeriğin benzersiz ID'si (YouTube ID veya içerik hash/slug). Benzersizdir. |
| `title` | string | **Evet** | İçeriğin başlığı. |
| `channel` / `channel_slug` | string | URL yoksa Evet | Kanal veya kaynak adı (URL'de geçilmişse URL önceliklidir). |
| `category` / `category_slug` | string | Hayır | Kategori / içerik türü (URL'de geçilmişse URL önceliklidir). |
| `content_type` | string | Hayır | `video`, `article`, `news`, `podcast`, `social`, `general` (belirtilmezse kategoriden otomatik algılanır). |
| `url` | string (URL) | Hayır | İçeriğe doğrudan bağlantı linki. |
| `published_at` | string (ISO 8601) | Hayır | Yayınlanma zamanı (ISO 8601). Boşsa sunucu saati atanır. |
| `summary` | string | Hayır | İçeriğin yapay zekâ veya kullanıcı özeti metni. |
| `key_moments` | array of objects | Hayır | Zaman damgalı önemli anlar listesi (`time`, `seconds`, `text`). |
| `channel_icon_url` | string (URL) | Hayır | Kanala özel logo/favicon bağlantısı. |
| `category_icon_url` | string (URL) | Hayır | Kategoriye özel logo/favicon bağlantısı. |

#### Başarılı Yanıt (Response):
```json
{
  "status": "ok",
  "action": "created",
  "item_id": "vid_001",
  "video_id": "vid_001",
  "category": "videodaldassak",
  "channel": "allahinyo",
  "content_type": "video",
  "title": "Yapay Zekâ ile Kodlama Rehberi",
  "feed_url": "/videodaldassak/allahinyo"
}
```

---

### 2. RSS Feed XML Akışları (FreshRSS & Okuyucular)

#### A) Kanal / Kaynak Feed'i (`GET /<kategori-slug>/<kanal-slug>?key=...`)

FreshRSS, Feedly, Inoreader, NetNewsWire veya herhangi bir RSS okuyucuda abone olmak için:

```
https://crss.armaganuzun.com/videodaldassak/allahinyo?key=crss_read_ANAHTARINIZ
```
veya YouTube için:
```
https://crss.armaganuzun.com/youtube/evrim-agaci?key=crss_read_ANAHTARINIZ
```

#### B) Toplu Kategori Feed'i (`GET /category/<kategori-slug>?key=...`)

Bir kategorideki (örn: `videodaldassak` veya `teknoloji`) **tüm kanalların** içeriklerini tek bir birleşik akışta toplamak için:

```
https://crss.armaganuzun.com/category/videodaldassak?key=crss_read_ANAHTARINIZ
```

#### C) Geriye Dönük Uyumluluk Linkleri:
- `https://crss.armaganuzun.com/youtube/<kanal-slug>?key=...`
- `https://crss.armaganuzun.com/channel/<kanal-slug>?key=...`
- `https://crss.armaganuzun.com/source/<kanal-slug>?key=...`

#### Dönen Standart RSS 2.0 XML Akışı Örneği:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>allahinyo - videodaldassak RSS</title>
    <link>https://crss.armaganuzun.com/videodaldassak/allahinyo</link>
    <description>allahinyo kaynağına ait yapay zekâ özetli ve zenginleştirilmiş RSS feed akışı.</description>
    <language>tr</language>
    <lastBuildDate>Thu, 12 Nov 2026 14:00:00 +0000</lastBuildDate>
    <image>
      <url>https://example.com/favicon.png</url>
      <title>allahinyo - videodaldassak RSS</title>
      <link>https://crss.armaganuzun.com/videodaldassak/allahinyo</link>
    </image>
    <atom:link href="https://crss.armaganuzun.com/videodaldassak/allahinyo" rel="self" type="application/rss+xml"/>
    <item>
      <title>Yapay Zekâ ile Kodlama Rehberi</title>
      <link>https://www.youtube.com/watch?v=vid_001</link>
      <guid isPermaLink="false">vid_001</guid>
      <pubDate>Thu, 12 Nov 2026 10:00:00 +0000</pubDate>
      <description><![CDATA[
        <h3>Özet</h3>
        <p>Bu bölümde yapay zekâ araçlarının modern geliştirme süreçlerine entegrasyonu inceleniyor.</p>
        <h3>Önemli Anlar</h3>
        <ul>
          <li><a href="https://youtu.be/vid_001?t=75" target="_blank"><strong>[01:15]</strong></a> Giriş ve Mimari</li>
          <li><a href="https://youtu.be/vid_001?t=260" target="_blank"><strong>[04:20]</strong></a> API Entegrasyonu</li>
        </ul>
        <hr/>
        <p><a href="https://www.youtube.com/watch?v=vid_001" target="_blank">İçeriği Görüntüle &rarr;</a></p>
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
