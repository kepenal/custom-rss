import os
from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Category, Channel, FeedItem, ApiKey
from .utils import generate_api_key, hash_token

# Admin Paneli Başlıkları (Docker Environment üzerinden özelleştirilebilir)
admin.site.site_header = os.getenv('DJANGO_ADMIN_SITE_HEADER', 'Custom RSS Hub Yönetimi')
admin.site.site_title = os.getenv('DJANGO_ADMIN_SITE_TITLE', 'Custom RSS Hub Yönetim Paneli')
admin.site.index_title = os.getenv('DJANGO_ADMIN_INDEX_TITLE', 'Akış, Kategori ve API Yönetimi')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('favicon_preview', 'name', 'slug', 'channel_count_display', 'updated_at')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('favicon_preview_large', 'created_at', 'updated_at')
    fields = ('name', 'slug', 'icon_url', 'favicon_preview_large', 'description', 'created_at', 'updated_at')

    def favicon_preview(self, obj):
        if obj.icon_url:
            return format_html(
                '<img src="{}" style="width:22px; height:22px; object-fit:contain; border-radius:4px; vertical-align:middle;" onerror="this.style.display=\'none\'" />',
                obj.icon_url
            )
        return format_html('<span style="color:#999; font-size:12px;">Logo Yok</span>')
    favicon_preview.short_description = 'Logo'

    def favicon_preview_large(self, obj):
        if obj.icon_url:
            return format_html(
                '<div style="display:flex; align-items:center; gap:12px; padding:6px; background:#f8f9fa; border:1px solid #ddd; border-radius:6px; width:fit-content;">'
                '<img src="{}" style="width:36px; height:36px; object-fit:contain; border-radius:4px;" />'
                '<span style="font-size:13px; color:#555;">Canlı Önizleme</span>'
                '</div>',
                obj.icon_url
            )
        return 'Henüz bir favicon veya logo URL girilmedi.'
    favicon_preview_large.short_description = 'Logo Önizleme'

    def channel_count_display(self, obj):
        return obj.channels.count()
    channel_count_display.short_description = 'Kanal / Kaynak Sayısı'


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('favicon_preview', 'name', 'category', 'slug', 'source_link', 'item_count_display', 'updated_at')
    list_filter = ('category',)
    search_fields = ('name', 'slug', 'source_url')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('favicon_preview_large', 'created_at', 'updated_at')
    fields = ('name', 'slug', 'category', 'icon_url', 'favicon_preview_large', 'source_url', 'created_at', 'updated_at')

    def favicon_preview(self, obj):
        effective_icon = obj.get_effective_icon_url()
        if effective_icon:
            is_inherited = not bool(obj.icon_url) and bool(obj.category and obj.category.icon_url)
            badge_title = 'Kategoriden miras alındı' if is_inherited else 'Kanalın kendi logosu'
            border_style = '2px dashed #17a2b8' if is_inherited else '1px solid #ddd'
            return format_html(
                '<img src="{}" title="{}" style="width:22px; height:22px; object-fit:contain; border-radius:4px; vertical-align:middle; border:{};" onerror="this.style.display=\'none\'" />',
                effective_icon, badge_title, border_style
            )
        return format_html('<span style="color:#999; font-size:12px;">Logo Yok</span>')
    favicon_preview.short_description = 'Logo'

    def favicon_preview_large(self, obj):
        effective_icon = obj.get_effective_icon_url()
        if effective_icon:
            if obj.icon_url:
                source_badge = '<span style="background:#28a745; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px; font-weight:bold;">Kanalın Kendi Logosu</span>'
            else:
                cat_name = obj.category.name if obj.category else 'Kategori'
                source_badge = f'<span style="background:#17a2b8; color:#fff; padding:2px 6px; border-radius:3px; font-size:11px; font-weight:bold;">{cat_name} Kategorisinden Alındı</span>'
            return format_html(
                '<div style="display:flex; align-items:center; gap:12px; padding:8px; background:#f8f9fa; border:1px solid #ddd; border-radius:6px; width:fit-content;">'
                '<img src="{}" style="width:36px; height:36px; object-fit:contain; border-radius:4px;" />'
                '<div>{}<div style="font-size:11px; color:#666; margin-top:3px;">{}</div></div>'
                '</div>',
                effective_icon, mark_safe(source_badge), effective_icon
            )
        return 'Henüz bir logo tanımlanmadı (Kategoriye eklenirse oradan otomatik alınır).'
    favicon_preview_large.short_description = 'Aktif Logo Durumu'

    def item_count_display(self, obj):
        return obj.items.count()
    item_count_display.short_description = 'İçerik Sayısı'

    def source_link(self, obj):
        if obj.source_url:
            return format_html('<a href="{}" target="_blank">Linke Git &rarr;</a>', obj.source_url)
        return '-'
    source_link.short_description = 'Kaynak Linki'


@admin.register(FeedItem)
class FeedItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel_with_cat', 'content_type_badge', 'published_at', 'item_link')
    list_filter = ('content_type', 'channel__category', 'channel', 'published_at')
    search_fields = ('title', 'item_id', 'summary')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'published_at'

    def channel_with_cat(self, obj):
        cat_name = obj.channel.category.name if obj.channel.category else 'Kategorisiz'
        return f'{obj.channel.name} ({cat_name})'
    channel_with_cat.short_description = 'Kaynak & Kategori'

    def content_type_badge(self, obj):
        colors = {
            'video': '#dc3545',
            'article': '#007bff',
            'news': '#ffc107; color:#212529',
            'podcast': '#6f42c1',
            'social': '#17a2b8',
            'general': '#6c757d',
        }
        bg = colors.get(obj.content_type, '#6c757d')
        style = f'background:{bg}; color:#fff; padding:3px 7px; border-radius:4px; font-size:11px; font-weight:bold;'
        if ';' in bg:
            style = f'background:{bg}; padding:3px 7px; border-radius:4px; font-size:11px; font-weight:bold;'
        return mark_safe(f'<span style="{style}">{obj.get_content_type_display()}</span>')
    content_type_badge.short_description = 'Tür'

    def item_link(self, obj):
        return format_html('<a href="{}" target="_blank">Aç &rarr;</a>', obj.url)
    item_link.short_description = 'İçerik Linki'


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
            '<strong>FreshRSS veya RSS Okuyucu için:</strong><br>'
            'Kategori Akışı: <code>https://crss.armaganuzun.com/category/&lt;kategori-slug&gt;?key=&lt;ANAHTAR&gt;</code><br>'
            'Kanal/Kaynak Akışı: <code>https://crss.armaganuzun.com/channel/&lt;kanal-slug&gt;?key=&lt;ANAHTAR&gt;</code> (veya <code>/youtube/...</code>)'
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
