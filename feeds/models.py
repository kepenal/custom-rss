from django.db import models
from django.utils import timezone
from .utils import normalize_channel_slug

class Channel(models.Model):
    name = models.CharField(max_length=255, verbose_name='Kanal Adı')
    slug = models.SlugField(max_length=255, unique=True, db_index=True, verbose_name='Kanal Slug')
    source_url = models.URLField(max_length=1000, blank=True, default='', verbose_name='YouTube Kanal/Kaynak URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Son Güncelleme Tarihi')

    class Meta:
        verbose_name = 'Kanal'
        verbose_name_plural = 'Kanallar'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = normalize_channel_slug(self.name)
        else:
            self.slug = normalize_channel_slug(self.slug)
        super().save(*args, **kwargs)


class VideoItem(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='videos', verbose_name='Kanal')
    video_id = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='YouTube Video ID')
    title = models.CharField(max_length=500, verbose_name='Video Başlığı')
    url = models.URLField(max_length=1000, verbose_name='Video URL')
    published_at = models.DateTimeField(db_index=True, verbose_name='Yayınlanma Tarihi')
    summary = models.TextField(blank=True, default='', verbose_name='Özet')
    key_moments = models.JSONField(default=list, blank=True, verbose_name='Önemli Anlar (Zaman Damgaları)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Kayıt Tarihi')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncellenme Tarihi')

    class Meta:
        verbose_name = 'Video'
        verbose_name_plural = 'Videolar'
        ordering = ['-published_at']

    def __str__(self):
        return f"{self.title} [{self.video_id}]"


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
