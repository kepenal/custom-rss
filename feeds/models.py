from django.db import models
from django.utils import timezone
from .utils import normalize_channel_slug


class Category(models.Model):
    name = models.CharField(max_length=255, verbose_name='Kategori Adı')
    slug = models.SlugField(max_length=255, unique=True, db_index=True, verbose_name='Kategori Slug')
    description = models.TextField(blank=True, default='', verbose_name='Kategori Açıklaması')
    icon_url = models.URLField(max_length=1000, blank=True, default='', verbose_name='Kategori Favicon / Logo URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Son Güncelleme Tarihi')

    class Meta:
        verbose_name = 'Kategori'
        verbose_name_plural = 'Kategoriler'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = normalize_channel_slug(self.name)
        else:
            self.slug = normalize_channel_slug(self.slug)
        super().save(*args, **kwargs)


class Channel(models.Model):
    name = models.CharField(max_length=255, verbose_name='Kanal / Kaynak Adı')
    slug = models.SlugField(max_length=255, unique=True, db_index=True, verbose_name='Kanal / Kaynak Slug')
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='channels',
        verbose_name='Kategori'
    )
    source_url = models.URLField(max_length=1000, blank=True, default='', verbose_name='Kaynak URL (YouTube, Web Sitesi vb.)')
    icon_url = models.URLField(max_length=1000, blank=True, default='', verbose_name='Özel Favicon / Logo URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Son Güncelleme Tarihi')

    class Meta:
        verbose_name = 'Kanal / Kaynak'
        verbose_name_plural = 'Kanallar & Kaynaklar'
        ordering = ['name']

    def __str__(self):
        cat_info = f" [{self.category.name}]" if self.category else ""
        return f"{self.name}{cat_info} ({self.slug})"

    def get_effective_icon_url(self):
        """
        Kanalın kendi icon_url'i varsa onu döndürür;
        yoksa bağlı olduğu kategorinin icon_url'ini döndürür.
        """
        if self.icon_url:
            return self.icon_url
        if self.category and self.category.icon_url:
            return self.category.icon_url
        return ''

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = normalize_channel_slug(self.name)
        else:
            self.slug = normalize_channel_slug(self.slug)
        if not self.category_id:
            default_cat, _ = Category.objects.get_or_create(
                slug='genel',
                defaults={'name': 'Genel'}
            )
            self.category = default_cat
        super().save(*args, **kwargs)

    @property
    def videos(self):
        return self.items


class FeedItem(models.Model):
    CONTENT_TYPE_CHOICES = (
        ('video', 'Video (YouTube vb.)'),
        ('article', 'Makale / Web Yazısı'),
        ('news', 'Haber / Bülten'),
        ('podcast', 'Podcast / Ses Kaydı'),
        ('social', 'Sosyal Medya (X/Twitter, Reddit vb.)'),
        ('general', 'Genel İçerik'),
    )

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='items', verbose_name='Kanal / Kaynak')
    item_id = models.CharField(max_length=255, unique=True, db_index=True, verbose_name='Öğe ID / GUID')
    content_type = models.CharField(max_length=32, choices=CONTENT_TYPE_CHOICES, default='video', verbose_name='İçerik Türü')
    title = models.CharField(max_length=500, verbose_name='Başlık')
    url = models.URLField(max_length=1000, verbose_name='İçerik URL')
    published_at = models.DateTimeField(db_index=True, verbose_name='Yayınlanma Tarihi')
    summary = models.TextField(blank=True, default='', verbose_name='AI Özeti')
    key_moments = models.JSONField(default=list, blank=True, verbose_name='Önemli Anlar / Maddeler (Key Moments / Highlights)')
    extra_data = models.JSONField(default=dict, blank=True, verbose_name='Ek Meta Veriler (JSON)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Kayıt Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')

    class Meta:
        verbose_name = 'İçerik Öğesi (Feed Item)'
        verbose_name_plural = 'İçerik Öğeleri'
        ordering = ['-published_at']

    def __str__(self):
        return f"[{self.get_content_type_display()}] {self.title} ({self.item_id})"

    @property
    def video_id(self):
        return self.item_id

    @video_id.setter
    def video_id(self, val):
        self.item_id = val


# Geriye dönük uyumluluk takma adı
VideoItem = FeedItem


class ApiKey(models.Model):
    KEY_TYPE_CHOICES = (
        ('write', 'Yazma Yetkisi (n8n API)'),
        ('read', 'Okuma Yetkisi (RSS Feed)'),
    )

    name = models.CharField(max_length=120, verbose_name='Anahtar Tanımı/İsim')
    key_hash = models.CharField(max_length=128, unique=True, verbose_name='Anahtar Hash (SHA-256)')
    key_prefix = models.CharField(max_length=12, verbose_name='Anahtar Ön Eki')
    key_type = models.CharField(max_length=10, choices=KEY_TYPE_CHOICES, default='read', verbose_name='Yetki Türü')
    is_active = models.BooleanField(default=True, verbose_name='Aktif mi?')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='Son Kullanılma')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')

    class Meta:
        verbose_name = 'API Anahtarı'
        verbose_name_plural = 'API Anahtarları'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.get_key_type_display()}] ({self.key_prefix}...)"
