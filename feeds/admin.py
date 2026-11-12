from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Channel, VideoItem, ApiKey
from .utils import generate_api_key, hash_token

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
        label='Özel Anahtar (Boş bırakılırsa otomatik güvenli anahtar üretilir)',
        help_text='Kendi belirlediğiniz bir token girebilirsiniz veya otomatik üretilmesini sağlayabilirsiniz.',
        widget=forms.TextInput(attrs={'style': 'width: 450px;'}),
    )

    class Meta:
        model = ApiKey
        fields = ('name', 'key_type', 'is_active')


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    form = ApiKeyAdminForm
    list_display = ('name', 'key_prefix_display', 'key_type', 'is_active', 'last_used_at', 'created_at')
    list_filter = ('key_type', 'is_active')
    readonly_fields = ('key_hash', 'key_prefix', 'last_used_at', 'created_at')
    search_fields = ('name', 'key_prefix')
    
    def key_prefix_display(self, obj):
        return f"{obj.key_prefix}..."
    key_prefix_display.short_description = 'Anahtar Ön Eki'

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
            
            messages.warning(
                request,
                format_html(
                    "<strong>YENİ API ANAHTARI ÜRETİLDİ:</strong> <code style='font-size:14px; background:#fff3cd; padding:3px 6px; border:1px solid #ffeeba;'>{}</code><br>"
                    "Bu anahtar sadece bir kez gösterilir! Güvenli bir yere kaydedin.",
                    raw_token
                )
            )
        super().save_model(request, obj, form, change)
