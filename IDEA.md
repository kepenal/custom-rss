# IDEA.md — YouTube RSS Toplayıcı ve Zenginleştirilmiş Feed Servisi

## Proje amacı

Arayüzü olmayan, Django ile geliştirilecek bir servis oluştur. n8n YouTube kanallarının RSS akışlarını izler; videoları özet ve önemli zaman damgalarıyla işler; ardından bu verileri servisin yazma API’sine gönderir. Servis kanal ve video kayıtlarını saklar ve her kanal için FreeRSS gibi RSS okuyucularının takip edebileceği bir RSS/XML feed’i sunar.

Bu proje temalı bir web sitesi değildir. Ana sayfa, pazarlama sayfası veya özel frontend geliştirme. Yönetim için Django Admin yeterlidir.

## Kullanıcı akışı

1. n8n bir video için JSON verisini yazma API’sine gönderir.
2. Servis isteğin yazma API anahtarını doğrular.
3. Kanal slug’ı sistemde yoksa kanal kaydı otomatik oluşturulur.
4. Video `video_id` üzerinden tekilleştirilir. Aynı video yeniden gelirse ikinci kayıt oluşmaz; güncelleme davranışı belgelenir.
5. RSS okuyucusu, kanala ait sabit feed URL’sini okuma API anahtarıyla çağırır.
6. Servis geçerli RSS 2.0 XML döndürür. Feed’de başlık, YouTube bağlantısı, yayın tarihi, özet ve varsa önemli zamanlar bulunur.

## Teknoloji ve kapsam

- Python ve Django kullan.
- Kalıcı veriler için PostgreSQL kullan; container yeniden başlasa da kanallar ve videolar korunmalı.
- RSS çıktısını Django endpoint’inden geçerli XML olarak üret.
- API ve feed yolları `/api/...` ve `/youtube/<channel_slug>` gibi açık, tutarlı bir şemaya sahip olsun.
- Endpoint URL’lerini, istek/yanıt şemalarını ve örnekleri README’de belgele.
- Gereksiz frontend, kullanıcı kaydı, tema ve görsel tasarım ekleme.

## Veri modeli

### Channel

- `name`: Görünen kanal adı
- `slug`: URL’de kullanılacak benzersiz, normalize edilmiş slug
- `source_url`: Varsa YouTube kanal veya kaynak feed URL’si
- `created_at`, `updated_at`

Kanal slug’ı boşluk, Türkçe karakter ve büyük/küçük harfler için tutarlı biçimde normalize edilmeli. Aynı kanala ait eşdeğer adlar farklı kanal kayıtları oluşturmamalı; API mümkünse n8n’den kararlı bir `channel_slug` veya YouTube kanal kimliği almalı.

### VideoItem

- `channel`: Channel ilişkisi
- `video_id`: YouTube video kimliği; global benzersiz olmalı
- `title`
- `url`
- `published_at`
- `summary`
- `key_moments`: Zaman damgası ve açıklamadan oluşan yapılandırılmış liste
- `description` veya n8n’den gelen diğer gerekli alanlar (yalnızca ihtiyaç varsa)
- `created_at`, `updated_at`

Django Admin’den kanallar ve videolar aranabilmeli, incelenebilmeli ve yönetilebilmeli. Admin liste sayfalarında kanal, başlık, video ID’si ve tarihler işe yarar biçimde gösterilsin.

## API tasarımı

### Yazma endpoint’i

n8n’in JSON ile video göndereceği, örneğin `POST /api/flows` adresinde bir endpoint oluştur. Tam endpoint ve şema kodlama sırasında kararlaştırılıp README’de sabitlensin.

Örnek payload:

```json
{
  "channel": {
    "name": "Eray Özkenar",
    "slug": "erayozkenar",
    "source_url": "https://www.youtube.com/@erayozkenar"
  },
  "video": {
    "video_id": "VIDEO_ID",
    "title": "Video başlığı",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "published_at": "2026-11-12T10:00:00Z",
    "summary": "Videonun özeti.",
    "key_moments": [
      {"time": "00:42", "seconds": 42, "text": "Önemli nokta"}
    ]
  }
}
```

Gereksinimler:

- Yazma anahtarı olmadan veya hatalı anahtarla istek reddedilmeli.
- JSON doğrulaması yapılmalı; anlaşılır HTTP durum kodları ve hata mesajları dönmeli.
- Aynı `video_id` tekrar geldiğinde çoğaltma olmamalı; işlem idempotent olmalı.
- Feed’e HTML/XML yerleştirilirken içerikler güvenli biçimde escape edilmeli.
- API anahtarı URL’ye yazılmamalı; HTTPS üzerinden Authorization header ile gönderilmeli.

### RSS okuma endpoint’i

Her kanal için kalıcı ve tahmin edilebilir bir URL sun. Örnek:

`GET /youtube/erayozkenar`

Endpoint yalnızca geçerli okuma API anahtarıyla erişilebilir olmalı ve RSS 2.0 XML döndürmeli. Örneğin RSS okuyucusu özel header gönderemiyorsa, `?key=...` veya ayrı bir token parametresi seçeneği sağla. Bu yöntem URL’yi gizli bir erişim bilgisi haline getirdiği için dokümantasyonda URL’nin paylaşılmaması gerektiğini belirt. Mümkünse okuyucunun desteklediği header tabanlı doğrulamayı da kullan.

Feed içeriği:

- Kanal/feed başlığı ve açıklaması
- Her video için benzersiz, kalıcı `guid` (tercihen YouTube `video_id`)
- Video başlığı ve YouTube bağlantısı
- Yayın tarihi (`pubDate`)
- Özet
- Önemli dakikalar; okunabilir açıklama veya HTML açıklama alanında

Doğru `Content-Type` (`application/rss+xml; charset=utf-8`) ve RSS tarih biçimi kullan. Feed sıralaması ve içerik limiti belgelenmiş ve tutarlı olsun.

## Anahtar yönetimi ve güvenlik

Yazma ve okuma anahtarları birbirinden ayrı yetkilere sahip olmalı. Yazma anahtarı n8n’in içerik eklemesini, okuma anahtarı feed erişimini sağlar; bir anahtar diğerinin yerine geçmemeli.

- Anahtarları kaynak koda veya Git’e koyma.
- Django Admin’de anahtarları güvenli biçimde yönetme veya environment üzerinden tekil anahtarlarla başlama seçeneği sağla. Tercih edilen yöntem ve anahtar rotasyonu README’de açıkça anlatılsın.
- Admin’de anahtarın düz metin değerini tekrar göstermemek ve veritabanında mümkünse hash saklamak tercih edilir.
- İsteklerde anahtarları loglama.
- Django `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, veritabanı bilgileri ve admin ilk kurulum bilgileri environment üzerinden alınmalı.
- Üretim ortamında `DEBUG=False` olmalı.
- Gerçek `.env` Git’e girmemeli; `.gitignore` ile dışarıda bırakılmalı.
- `.env.example` yalnızca değişken adlarını ve sahte örnekleri içermeli.

## Django Admin ve ilk superuser

Django Admin yalnızca sistem yönetimi için kullanılacak. İlk superuser’ı container’ın ilk başlangıcında environment değişkenleri verilmişse otomatik oluştur:

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`

Bu işlem idempotent olmalı: kullanıcı zaten varsa her başlangıçta tekrar oluşturmaya veya parolasını değiştirmeye çalışma. Zorunlu bilgiler yoksa güvenli biçimde ne yapılacağını README’de açıkla; varsayılan, tahmin edilebilir parola kullanma. Migration’lar başlatma akışında güvenli biçimde uygulanmalı. Uygulama normal çalışmaya başlamadan önce veritabanı hazır olmasını beklemeli.

## Docker ve Portainer dağıtımı

- Üretim kullanımı için `Dockerfile` ve `compose.yml` sağla.
- Django uygulaması üretim WSGI sunucusuyla çalışmalı; `runserver` kullanma.
- PostgreSQL için kalıcı Docker volume tanımla.
- Servis sağlık kontrolü ve veritabanı hazır olma kontrolü ekle.
- Portainer Stack ile kuruluma uygun, okunabilir Compose dosyası hazırla.
- Uygulamanın dinlediği port environment üzerinden ayarlanabilir olsun. Nginx reverse proxy kullanıldığında uygulamayı internete doğrudan açmak zorunlu olmasın; proxy ile aynı Docker ağına bağlanabilsin.
- Portainer’ın kendi yönetim portlarını bu uygulamanın Compose dosyasında açma veya yönetmeye çalışma.
- Compose değişkenlerinin tamamını `.env.example` içinde açıkla.

## Nginx reverse proxy

Projede örnek Nginx server config’i bulunsun veya README’de verilsin. Nginx `/api/` ve kanal feed yollarını Django servisine proxy etsin; Host ve gerçek istemci IP’si gibi standart proxy header’larını iletsin. HTTPS’in Nginx tarafında sonlandırılacağı kurulum için gerekli başlıkları ve örnek domain ayarını belgele. Örnekte gerçek sunucuya ait sır veya sertifika bulunmasın.

## GitHub ve depo düzeni

Depo private GitHub reposuna aktarılmaya uygun olmalı. Gerçek parola, API anahtarı, token, veritabanı parolası veya kişisel sunucu bilgisi commit edilmemeli. En azından şu dosyalar bulunmalı:

- Django proje kodu
- `Dockerfile`
- `compose.yml`
- `.env.example`
- `.gitignore`
- `README.md` (kurulum, environment değişkenleri, API payload örneği, FreeRSS’e feed ekleme ve Nginx/Portainer dağıtımı)
- Nginx örnek config’i

## Kabul ölçütleri

1. Boş veritabanıyla Compose/Portainer üzerinden ayağa kalkabilmeli.
2. Environment bilgileri verilmişse ilk admin hesabı güvenli ve tekrarsız oluşturulmalı.
3. Geçerli yazma anahtarıyla yeni kanal ve video eklenebilmeli.
4. Aynı video tekrar gönderildiğinde mükerrer kayıt oluşmamalı.
5. Hatalı veya eksik yazma anahtarıyla içerik eklenememeli.
6. Kanal feed’i okuma anahtarıyla erişilebilir ve RSS okuyucusunun anlayacağı geçerli XML olmalı.
7. Okuma anahtarı yazma endpoint’inde, yazma anahtarı da korumalı feed’de yetki vermemeli.
8. Django Admin’den kanal ve video kayıtları yönetilebilmeli.
9. Container yeniden başlatıldığında veriler kaybolmamalı.
10. Nginx reverse proxy arkasında çalıştırma adımları belgelenmiş olmalı.
11. Kaynak kodda gerçek sır bulunmamalı.

## Kodlama asistanı için çalışma notu

Önce repository içeriğini ve mevcut talimat dosyalarını incele. Sonra küçük, anlaşılır bir Django uygulaması kur; modelleri, migration’ları, API doğrulamasını, feed üretimini, admin ekranlarını ve dağıtım dosyalarını tamamla. Proje için gerekli olmayan frontend veya servisler ekleme. Yapılan değişiklikleri ve çalıştırma adımlarını README’de açıkla. Değişiklikleri doğrulamak için uygun kontrolleri çalıştır ve sonuçları raporla.
