import json
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .auth import authenticate_request
from .models import Category, Channel, FeedItem
from .utils import normalize_channel_slug


def build_rss_xml(title, link, description, items, request_url, icon_url=''):
    """
    RSS 2.0 XML oluşturucu helper.
    FreshRSS ve diğer okuyucular için standart <image>, <atom:icon> ve <atom:logo> etiketlerini ekler.
    """
    build_date_str = date_format(timezone.now(), 'r')
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        f'    <title>{xml_escape(title)}</title>',
        f'    <link>{xml_escape(link)}</link>',
        f'    <description>{xml_escape(description)}</description>',
        '    <language>tr</language>',
        f'    <lastBuildDate>{build_date_str}</lastBuildDate>',
        f'    <atom:link href="{xml_escape(request_url)}" rel="self" type="application/rss+xml" />',
    ]

    # Favicon / Logo desteği (FreshRSS, Feedly vb.)
    if icon_url:
        xml_lines.extend([
            '    <image>',
            f'      <url>{xml_escape(icon_url)}</url>',
            f'      <title>{xml_escape(title)}</title>',
            f'      <link>{xml_escape(link)}</link>',
            '    </image>',
            f'    <atom:icon>{xml_escape(icon_url)}</atom:icon>',
            f'    <atom:logo>{xml_escape(icon_url)}</atom:logo>',
        ])

    for item in items:
        pub_date_str = date_format(item.published_at, 'r')
        html_parts = []
        if item.summary:
            html_parts.append(f"<h3>Özet</h3><p>{xml_escape(item.summary)}</p>")

        if item.key_moments:
            is_video = (item.content_type == 'video')
            section_title = "Önemli Anlar" if is_video else "Önemli Noktalar & Başlıklar"
            html_parts.append(f"<h3>{section_title}</h3><ul>")
            for km in item.key_moments:
                if isinstance(km, dict):
                    t_label = xml_escape(str(km.get('time', '')).strip())
                    t_sec = km.get('seconds', 0)
                    t_text = xml_escape(str(km.get('text', '')).strip())

                    if is_video and t_sec and int(t_sec) > 0:
                        time_url = f"https://youtu.be/{item.item_id}?t={t_sec}"
                        time_tag = f"<a href=\"{time_url}\" target=\"_blank\"><strong>[{t_label}]</strong></a> " if t_label else ""
                        html_parts.append(f"<li>{time_tag}{t_text}</li>")
                    else:
                        badge = f"<strong>[{t_label}]</strong> " if t_label else ""
                        html_parts.append(f"<li>{badge}{t_text}</li>")
                elif isinstance(km, str):
                    html_parts.append(f"<li>{xml_escape(km)}</li>")
            html_parts.append("</ul>")

        cta_text = "YouTube'da İzle &rarr;" if item.content_type == 'video' else "Kaynağa Git &rarr;"
        html_parts.append(f"<p><a href=\"{xml_escape(item.url)}\" target=\"_blank\">{cta_text}</a></p>")
        description_html = "\n".join(html_parts)

        xml_lines.append('    <item>')
        xml_lines.append(f'      <title>{xml_escape(item.title)}</title>')
        xml_lines.append(f'      <link>{xml_escape(item.url)}</link>')
        xml_lines.append(f'      <guid isPermaLink="false">{item.item_id}</guid>')
        xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
        xml_lines.append(f'      <description><![CDATA[{description_html}]]></description>')
        xml_lines.append('    </item>')

    xml_lines.append('  </channel>')
    xml_lines.append('</rss>')
    return '\n'.join(xml_lines)


@method_decorator(csrf_exempt, name='dispatch')
class FlowIngestView(View):
    """
    n8n ve otomasyon araçlarından video, makale, haber, podcast vb. tüm AI özet verilerini
    alan evrensel POST API ucu.
    """
    def post(self, request, *args, **kwargs):
        is_authed, err_msg = authenticate_request(request, required_type='write')
        if not is_authed:
            return JsonResponse({'status': 'error', 'message': err_msg}, status=401)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Geçersiz JSON gövdesi: {str(e)}'}, status=400)

        item_id = str(payload.get('item_id') or payload.get('video_id') or payload.get('id') or '').strip()
        title = str(payload.get('title', '')).strip()
        channel_name = str(
            payload.get('channel') or
            payload.get('source') or
            payload.get('channel_name') or
            payload.get('channel_title') or
            ''
        ).strip()
        channel_slug = str(payload.get('channel_slug') or payload.get('source_slug') or '').strip()
        category_raw = str(payload.get('category') or payload.get('category_name') or '').strip()
        category_slug = str(payload.get('category_slug') or '').strip()
        content_type = str(payload.get('content_type', '')).strip().lower()

        if not item_id:
            item_url = str(payload.get('url', '')).strip()
            if item_url:
                item_id = item_url
            else:
                return JsonResponse({'status': 'error', 'message': "'video_id' veya 'item_id' zorunludur."}, status=400)

        if not title:
            return JsonResponse({'status': 'error', 'message': "'title' (başlık) zorunludur."}, status=400)

        if not content_type:
            if payload.get('video_id') or payload.get('key_moments'):
                content_type = 'video'
            else:
                content_type = 'general'

        valid_types = [c[0] for c in FeedItem.CONTENT_TYPE_CHOICES]
        if content_type not in valid_types:
            content_type = 'general'

        # Kategori Yönetimi
        category = None
        if category_raw or category_slug:
            cat_target_slug = category_slug if category_slug else normalize_channel_slug(category_raw)
            if cat_target_slug:
                category, _ = Category.objects.get_or_create(
                    slug=cat_target_slug,
                    defaults={'name': category_raw or cat_target_slug}
                )
                if category_raw and category.name != category_raw:
                    category.name = category_raw
                    category.save(update_fields=['name', 'updated_at'])

        # Kanal / Kaynak Yönetimi
        if not channel_name and not channel_slug:
            channel_name = 'Genel Kaynak'

        target_slug = channel_slug if channel_slug else normalize_channel_slug(channel_name)
        if not target_slug:
            target_slug = 'default'

        channel_source_url = str(payload.get('channel_url') or payload.get('source_url') or '').strip()
        channel_icon_url = str(payload.get('channel_icon_url') or payload.get('icon_url') or '').strip()

        channel, created_channel = Channel.objects.get_or_create(
            slug=target_slug,
            defaults={
                'name': channel_name or target_slug,
                'source_url': channel_source_url,
                'icon_url': channel_icon_url,
                'category': category,
            }
        )

        updates = []
        if channel_name and channel.name != channel_name:
            channel.name = channel_name
            updates.append('name')
        if channel_source_url and not channel.source_url:
            channel.source_url = channel_source_url
            updates.append('source_url')
        if channel_icon_url and not channel.icon_url:
            channel.icon_url = channel_icon_url
            updates.append('icon_url')
        if category and channel.category is None:
            channel.category = category
            updates.append('category')
        if updates:
            updates.append('updated_at')
            channel.save(update_fields=updates)

        item_url = str(payload.get('url', '')).strip()
        if not item_url:
            if content_type == 'video':
                item_url = f"https://www.youtube.com/watch?v={item_id}"
            else:
                item_url = channel.source_url or 'https://crss.armaganuzun.com'

        published_at_raw = payload.get('published_at')
        published_at = None
        if published_at_raw:
            if isinstance(published_at_raw, (int, float)):
                published_at = datetime.fromtimestamp(published_at_raw, tz=timezone.utc)
            elif isinstance(published_at_raw, str):
                try:
                    clean_iso = published_at_raw.replace('Z', '+00:00')
                    published_at = datetime.fromisoformat(clean_iso)
                except Exception:
                    published_at = timezone.now()
        if not published_at:
            published_at = timezone.now()

        summary = str(payload.get('summary', '')).strip()
        raw_key_moments = payload.get('key_moments', [])
        if not isinstance(raw_key_moments, list):
            raw_key_moments = []

        sanitized_key_moments = []
        for item in raw_key_moments:
            if isinstance(item, dict):
                sanitized_key_moments.append({
                    'time': str(item.get('time', '')).strip(),
                    'seconds': item.get('seconds', 0),
                    'text': str(item.get('text', '')).strip()
                })
            elif isinstance(item, str):
                sanitized_key_moments.append({
                    'time': '',
                    'seconds': 0,
                    'text': item.strip()
                })

        extra_data = payload.get('extra') or payload.get('extra_data') or {}
        if not isinstance(extra_data, dict):
            extra_data = {}

        feed_item, created = FeedItem.objects.update_or_create(
            item_id=item_id,
            defaults={
                'channel': channel,
                'content_type': content_type,
                'title': title,
                'url': item_url,
                'published_at': published_at,
                'summary': summary,
                'key_moments': sanitized_key_moments,
                'extra_data': extra_data,
            }
        )

        return JsonResponse({
            'status': 'ok',
            'action': 'created' if created else 'updated',
            'item_id': feed_item.item_id,
            'video_id': feed_item.item_id,
            'channel': channel.slug,
            'category': category.slug if category else (channel.category.slug if channel.category else None),
            'content_type': feed_item.content_type,
            'title': feed_item.title,
        }, status=201 if created else 200)


class ChannelRssFeedView(View):
    """
    Kanal / Kaynak bazlı zenginleştirilmiş RSS 2.0 XML akışı sunar.
    Favicon hiyerarşisi: Kanalın kendi logosu varsa o, yoksa kategorisinin logosu gönderilir.
    """
    def get(self, request, channel_slug, *args, **kwargs):
        is_authed, err_msg = authenticate_request(request, required_type='read')
        if not is_authed:
            return HttpResponse(
                f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><error><code>401</code><message>{xml_escape(err_msg)}</message></error>",
                content_type='application/xml; charset=utf-8',
                status=401
            )

        clean_slug = normalize_channel_slug(channel_slug)
        try:
            channel = Channel.objects.select_related('category').get(slug=clean_slug)
        except Channel.DoesNotExist:
            return HttpResponse(
                f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><error><code>404</code><message>'{xml_escape(channel_slug)}' adlı kanal/kaynak bulunamadı.</message></error>",
                content_type='application/xml; charset=utf-8',
                status=404
            )

        limit = getattr(settings, 'RSS_FEED_LIMIT', 50)
        items = channel.items.all().order_by('-published_at')[:limit]

        title = f"{channel.name} - RSS Feed"
        link = channel.source_url or request.build_absolute_uri()
        desc = f"{channel.name} kaynağına ait yapay zekâ özetli ve zenginleştirilmiş RSS akışı."
        effective_icon = channel.get_effective_icon_url()

        xml_content = build_rss_xml(
            title=title,
            link=link,
            description=desc,
            items=items,
            request_url=request.build_absolute_uri(),
            icon_url=effective_icon
        )
        return HttpResponse(xml_content, content_type='application/rss+xml; charset=utf-8')


class CategoryRssFeedView(View):
    """
    Kategori bazlı (örn: bilim, yazilim, haber) tüm kaynakların özetlerini birleştiren
    ortak RSS 2.0 XML akışı sunar.
    """
    def get(self, request, category_slug, *args, **kwargs):
        is_authed, err_msg = authenticate_request(request, required_type='read')
        if not is_authed:
            return HttpResponse(
                f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><error><code>401</code><message>{xml_escape(err_msg)}</message></error>",
                content_type='application/xml; charset=utf-8',
                status=401
            )

        clean_slug = normalize_channel_slug(category_slug)
        try:
            category = Category.objects.get(slug=clean_slug)
        except Category.DoesNotExist:
            return HttpResponse(
                f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><error><code>404</code><message>'{xml_escape(category_slug)}' adlı kategori bulunamadı.</message></error>",
                content_type='application/xml; charset=utf-8',
                status=404
            )

        limit = getattr(settings, 'RSS_FEED_LIMIT', 50)
        items = FeedItem.objects.filter(channel__category=category).order_by('-published_at')[:limit]

        title = f"{category.name} - Kategori RSS Akışı"
        link = request.build_absolute_uri()
        desc = category.description or f"{category.name} kategorisindeki tüm kaynaklara ait yapay zekâ özetli RSS akışı."
        icon_url = category.icon_url

        xml_content = build_rss_xml(
            title=title,
            link=link,
            description=desc,
            items=items,
            request_url=request.build_absolute_uri(),
            icon_url=icon_url
        )
        return HttpResponse(xml_content, content_type='application/rss+xml; charset=utf-8')
