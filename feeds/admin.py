import os
from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Channel, VideoItem, ApiKey
from .utils import generate_api_key, hash_token

# Admin Paneli Başlıkları (Docker Environment üzerinden özelleştirilebilir)
admin.site.site_header = os.getenv('DJANGO_ADMIN_SITE_HEADER', 'Custom RSS Yönetimi')
admin.site.site_title = os.getenv('DJANGO_ADMIN_SITE_TITLE', 'Custom RSS Yönetim Paneli')
admin.site.index_title = os.getenv('DJANGO_ADMIN_INDEX_TITLE', 'Akış ve API Yönetimi')

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'source_link', 'video_count_display', 'updated_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    
    def video_count_display(self, obj):
        return obj.videos.count()
    video_count_display.short_description = 'Video Sayısı'
    
    def source_link(self, obj):
        if obj.source_url:
            return format_html('<a href="{}" target="_blank">Linke Git</a>', obj.source_url)
        return '-'
    source_link.short_description = 'YouTube Linki'


@admin.register(VideoItem)
class VideoItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel', 'video_id', 'published_at', 'watch_link')
    list_filter = ('channel', 'published_at')
    search_fields = ('title', 'video_id', 'summary')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'published_at'
    
    def watch_link(self, obj):
        return format_html('<a href="{}" target="_blank">İzle</a>', obj.url)
    watch_link.short_description = 'YouTube'


class ApiKeyAdminForm(forms.ModelForm):
    raw_token = forms.CharField(
        required=False,
        label='Özel Anahtar Değeri (Opsiyonel)',
        help_text='Boş bırakırsanız sistem otomatik olarak yüksek entropili, güvenli bir anahtar üretecektir.',
        widget=forms.TextInput(attrs={'style': 'width: 480px; padding: 6px;', 'placeholder': 'Otomatik üretim için boş bırakın...'}),
    )

    class Meta:
        model = ApiKey
        fields = ('name', 'key_type', 'is_active')


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    form = ApiKeyAdminForm
    list_display = ('name', 'key_prefix_display', 'key_type_badge', 'is_active', 'last_used_at', 'created_at')
    list_filter = ('key_type', 'is_active')
    readonly_fields = ('key_hash', 'key_prefix', 'last_used_at', 'created_at', 'usage_guide')
    search_fields = ('name', 'key_prefix')
    
    def key_prefix_display(self, obj):
        return f"{obj.key_prefix}..."
    key_prefix_display.short_description = 'Anahtar Ön Eki'

    def key_type_badge(self, obj):
        if obj.key_type == 'write':
            return mark_safe('<span style="background:#d1ecf1; color:#0c5460; padding:3px 8px; border-radius:4px; font-weight:bold;">Yazma (n8n API)</span>')
        return mark_safe('<span style="background:#d4edda; color:#155724; padding:3px 8px; border-radius:4px; font-weight:bold;">Okuma (RSS Feed)</span>')
    key_type_badge.short_description = 'Yetki Türü'

    def usage_guide(self, obj):
        if not obj.pk:
            return '-'
        if obj.key_type == 'write':
            return mark_safe(
                '<div style="line-height:1.6;">'
                '<strong>n8n veya API İstemcisi için:</strong><br>'
                'Header: <code>Authorization: Bearer &lt;ANAHTAR&gt;</code> veya <code>X-API-Key: &lt;ANAHTAR&gt;</code><br>'
                'Endpoint: <code>POST /api/flows</code>'
                '</div>'
            )
        return mark_safe(
            '<div style="line-height:1.6;">'
            '<strong>FreeRSS veya RSS Okuyucu için:</strong><br>'
            'Feed URL: <code>https://crss.armaganuzun.com/youtube/&lt;kanal-slug&gt;?key=&lt;ANAHTAR&gt;</code>'
            '</div>'
        )
    usage_guide.short_description = 'Kullanım Kılavuzu'

    def save_model(self, request, obj, form, change):
        raw_token = form.cleaned_data.get('raw_token', '').strip()
        if not change or raw_token:
            if not raw_token:
                prefix = 'crss_write' if obj.key_type == 'write' else 'crss_read'
                raw_token, key_hash, key_prefix = generate_api_key(prefix=prefix)
            else:
                key_hash = hash_token(raw_token)
                key_prefix = raw_token[:8]
                
            obj.key_hash = key_hash
            obj.key_prefix = key_prefix
            
            instructions = mark_safe((
                "n8n HTTP Request node başlığına <code>Authorization: Bearer {}</code> ekleyin."
                if obj.key_type == 'write' else
                "RSS okuyucunuzun URL alanına <code>?key={}</code> parametresini ekleyin."
            ).format(raw_token))

            messages.warning(
                request,
                format_html(
                    "<div style='font-size:14px;'>"
                    "<strong>✅ YENİ API ANAHTARI ÜRETİLDİ:</strong><br>"
                    "<input type='text' readonly value='{}' style='font-size:15px; font-family:monospace; background:#fff3cd; color:#856404; padding:6px 10px; width:520px; border:1px solid #ffeeba; margin:6px 0;' onclick='this.select();' /><br>"
                    "⚠️ <em>Bu anahtar veritabanında SHA-256 olarak saklanır ve tekrar görüntülenemez. Lütfen kopyalayıp güvenli bir yere kaydedin.</em><br>"
                    "<strong>Nasıl Kullanılır?</strong> {}"
                    "</div>",
                    raw_token, instructions
                )
            )
        super().save_model(request, obj, form, change)
