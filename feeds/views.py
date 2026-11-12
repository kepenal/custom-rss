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
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">',
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
            summary_clean = str(item.summary).strip()
            # HTML etiketleri (<b>, <a>, <p>, <br> vb.) CDATA içinde korunmalı,
            # xml_escape YAPILMAMALIDIR. Aksi halde FreshRSS ve RSS okuyucularda
            # etiketler düz metin (&lt;b&gt;) olarak render edilir.
            if summary_clean.startswith("<p") or summary_clean.startswith("<div"):
                html_parts.append(f"<h3>Özet</h3>\n{summary_clean}")
            else:
                # Düz metin ise ve blok etiket içermiyorsa satır sonlarını işle
                if "\n" in summary_clean and not any(tag in summary_clean.lower() for tag in ["<p", "<div", "<br", "<ul", "<ol"]):
                    paragraphs = [p.strip() for p in summary_clean.split("\n\n") if p.strip()]
                    if len(paragraphs) > 1:
                        formatted_p = "\n".join(f"<p>{p.replace(chr(10), "<br/>")}</p>" for p in paragraphs)
                        html_parts.append(f"<h3>Özet</h3>\n{formatted_p}")
                    else:
                        formatted_br = summary_clean.replace("\n", "<br/>")
                        html_parts.append(f"<h3>Özet</h3><p>{formatted_br}</p>")
                else:
                    html_parts.append(f"<h3>Özet</h3><p>{summary_clean}</p>")

        if item.key_moments:
            is_video = (item.content_type == 'video')
            section_title = "Önemli Anlar" if is_video else "Önemli Noktalar & Başlıklar"
            html_parts.append(f"<h3>{section_title}</h3><ul>")
            for km in item.key_moments:
                if isinstance(km, dict):
                    t_label = xml_escape(str(km.get('time', '')).strip())
                    t_sec = km.get('seconds', 0)
                    t_text = str(km.get('text', '')).strip()

                    if is_video and t_sec and int(t_sec) > 0 and not str(item.item_id).startswith('http'):
                        time_url = f"https://youtu.be/{item.item_id}?t={t_sec}"
                        time_tag = f"<a href=\"{time_url}\" target=\"_blank\"><strong>[{t_label}]</strong></a> " if t_label else ""
                        html_parts.append(f"<li>{time_tag}{t_text}</li>")
                    else:
                        badge = f"<strong>[{t_label}]</strong> " if t_label else ""
                        html_parts.append(f"<li>{badge}{t_text}</li>")
                elif isinstance(km, str):
                    html_parts.append(f"<li>{str(km).strip()}</li>")
            html_parts.append("</ul>")

        cta_text = "YouTube'da İzle &rarr;" if item.content_type == 'video' else "Kaynağa Git &rarr;"
        html_parts.append(f"<p><a href=\"{xml_escape(item.url)}\" target=\"_blank\">{cta_text}</a></p>")
        description_html = "\n".join(html_parts)

        xml_lines.append('    <item>')
        xml_lines.append(f'      <title>{xml_escape(item.title)}</title>')
        xml_lines.append(f'      <link>{xml_escape(item.url)}</link>')
        xml_lines.append(f'      <guid isPermaLink="false">{item.item_id}</guid>')
        xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
        safe_cdata_html = description_html.replace("]]>", "]]]]><![CDATA[>")
        xml_lines.append(f'      <description><![CDATA[{safe_cdata_html}]]></description>')
        xml_lines.append(f'      <content:encoded><![CDATA[{safe_cdata_html}]]></content:encoded>')
        xml_lines.append('    </item>')

    xml_lines.append('  </channel>')
    xml_lines.append('</rss>')
    return '\n'.join(xml_lines)


@method_decorator(csrf_exempt, name='dispatch')
class FlowIngestView(View):
    """
    n8n ve otomasyon araçlarından video, makale, haber, podcast vb. tüm AI özet verilerini
    alan evrensel POST Ingest API ucu.

    URL biçimleri:
      - POST /<category_slug>/<channel_slug> (örn: /videodaldassak/allahinyo)
      - POST /api/flows/<category_slug>/<channel_slug>
      - POST /api/<category_slug>/<channel_slug>
      - POST /api/flows (Kategori ve kanal JSON gövdesinden veya varsayılandan alınır)
    """
    def post(self, request, category_slug=None, channel_slug=None, *args, **kwargs):
        is_authed, err_msg = authenticate_request(request, required_type='write')
        if not is_authed:
            return JsonResponse({'status': 'error', 'message': err_msg}, status=401)

        try:
            payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Geçersiz JSON gövdesi: {str(e)}'}, status=400)

        item_id = str(payload.get('item_id') or payload.get('video_id') or payload.get('id') or '').strip()
        title = str(payload.get('title', '')).strip()

        if not item_id:
            item_url = str(payload.get('url', '')).strip()
            if item_url:
                item_id = item_url
            else:
                return JsonResponse({'status': 'error', 'message': "'video_id' veya 'item_id' zorunludur."}, status=400)

        if not title:
            return JsonResponse({'status': 'error', 'message': "'title' (başlık) zorunludur."}, status=400)

        # 1. Kategori Belirleme ve Otomatik Oluşturma (get_or_create)
        # Sıralama: URL category_slug > Query param > JSON category_slug > JSON category > JSON category_name
        raw_cat = (
            category_slug or
            request.GET.get('category_slug') or
            request.GET.get('category') or
            payload.get('category_slug') or
            payload.get('category') or
            payload.get('category_name') or
            ''
        )
        raw_cat = str(raw_cat).strip()

        # Kategori verilmemişse akıllı varsayılan (Kategoriler asla boş kalmaz)
        if not raw_cat:
            if payload.get('video_id') or str(payload.get('content_type', '')).lower() == 'video':
                raw_cat = 'youtube'
            else:
                raw_cat = 'genel'

        clean_cat_slug = normalize_channel_slug(raw_cat)
        if not clean_cat_slug:
            clean_cat_slug = 'genel'

        KNOWN_CATEGORY_NAMES = {
            'youtube': 'YouTube',
            'ai': 'Yapay Zekâ',
            'rss': 'RSS',
            'api': 'API',
        }

        cat_name = str(payload.get('category_name') or payload.get('category') or '').strip()
        if not cat_name or normalize_channel_slug(cat_name) == clean_cat_slug:
            cat_name = KNOWN_CATEGORY_NAMES.get(clean_cat_slug, clean_cat_slug.replace('-', ' ').title())

        cat_icon = str(payload.get('category_icon_url') or '').strip()

        category, _ = Category.objects.get_or_create(
            slug=clean_cat_slug,
            defaults={'name': cat_name, 'icon_url': cat_icon}
        )
        cat_updates = []
        if cat_name and category.name == clean_cat_slug.replace('-', ' ').title() and category.name != cat_name:
            category.name = cat_name
            cat_updates.append('name')
        if cat_icon and not category.icon_url:
            category.icon_url = cat_icon
            cat_updates.append('icon_url')
        if cat_updates:
            cat_updates.append('updated_at')
            category.save(update_fields=cat_updates)

        # 2. Kanal / Kaynak Belirleme ve Otomatik Oluşturma (get_or_create)
        # Sıralama: URL channel_slug > Query param > JSON channel_slug > JSON source_slug > JSON channel > JSON source
        raw_chan = (
            channel_slug or
            request.GET.get('channel_slug') or
            request.GET.get('source_slug') or
            payload.get('channel_slug') or
            payload.get('source_slug') or
            payload.get('channel') or
            payload.get('source') or
            payload.get('channel_name') or
            payload.get('channel_title') or
            ''
        )
        raw_chan = str(raw_chan).strip()
        if not raw_chan:
            raw_chan = 'default'

        clean_chan_slug = normalize_channel_slug(raw_chan)
        if not clean_chan_slug:
            clean_chan_slug = 'default'

        chan_name = str(
            payload.get('channel') or
            payload.get('source') or
            payload.get('channel_name') or
            payload.get('channel_title') or
            ''
        ).strip()
        if not chan_name or normalize_channel_slug(chan_name) == clean_chan_slug:
            chan_name = clean_chan_slug.replace('-', ' ').title()

        channel_source_url = str(payload.get('channel_url') or payload.get('source_url') or '').strip()
        channel_icon_url = str(payload.get('channel_icon_url') or payload.get('icon_url') or '').strip()

        channel, created_channel = Channel.objects.get_or_create(
            slug=clean_chan_slug,
            defaults={
                'name': chan_name,
                'source_url': channel_source_url,
                'icon_url': channel_icon_url,
                'category': category,
            }
        )

        chan_updates = []
        if chan_name and channel.name == clean_chan_slug.replace('-', ' ').title() and channel.name != chan_name:
            channel.name = chan_name
            chan_updates.append('name')
        if channel_source_url and not channel.source_url:
            channel.source_url = channel_source_url
            chan_updates.append('source_url')
        if channel_icon_url and not channel.icon_url:
            channel.icon_url = channel_icon_url
            chan_updates.append('icon_url')
        # Kategori ilişkisini garantile
        if category and (channel.category is None or category_slug):
            if channel.category != category:
                channel.category = category
                chan_updates.append('category')
        if chan_updates:
            chan_updates.append('updated_at')
            channel.save(update_fields=chan_updates)

        # 3. İçerik Türü (content_type)
        content_type = str(payload.get('content_type', '')).strip().lower()
        valid_types = [c[0] for c in FeedItem.CONTENT_TYPE_CHOICES]
        if not content_type or content_type not in valid_types:
            if clean_cat_slug in ['youtube', 'video', 'videolar'] or 'video' in clean_cat_slug or payload.get('video_id') or payload.get('key_moments'):
                content_type = 'video'
            elif clean_cat_slug in ['article', 'makale', 'yazi', 'blog']:
                content_type = 'article'
            elif clean_cat_slug in ['news', 'haber', 'haberler', 'bulten']:
                content_type = 'news'
            elif clean_cat_slug in ['podcast', 'ses', 'audio']:
                content_type = 'podcast'
            elif clean_cat_slug in ['social', 'sosyal', 'twitter', 'x', 'reddit']:
                content_type = 'social'
            else:
                content_type = 'general'

        # 4. Öğe Bağlantısı (URL)
        item_url = str(payload.get('url', '')).strip()
        if not item_url:
            if content_type == 'video':
                if item_id.startswith('http://') or item_id.startswith('https://'):
                    item_url = item_id
                else:
                    item_url = f"https://www.youtube.com/watch?v={item_id}"
            else:
                item_url = channel.source_url or 'https://crss.armaganuzun.com'

        # 5. Tarih ve Zaman
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

        # 6. Özet ve Önemli Anlar / Maddeler
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

        # 7. FeedItem Upsert
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

        feed_url = f"/{category.slug}/{channel.slug}" if category else f"/channel/{channel.slug}"

        return JsonResponse({
            'status': 'ok',
            'action': 'created' if created else 'updated',
            'item_id': feed_item.item_id,
            'video_id': feed_item.item_id,
            'channel': channel.slug,
            'category': category.slug if category else None,
            'content_type': feed_item.content_type,
            'title': feed_item.title,
            'feed_url': feed_url,
        }, status=201 if created else 200)


class ChannelRssFeedView(View):
    """
    Kanal / Kaynak bazlı zenginleştirilmiş RSS 2.0 XML akışı sunar.
    URL formatları:
      - /<category_slug>/<channel_slug> (örn: /videodaldassak/allahinyo veya /youtube/evrim-agaci)
      - /channel/<channel_slug>
      - /source/<channel_slug>
      - /youtube/<channel_slug>
    Favicon hiyerarşisi: Kanalın kendi logosu varsa o, yoksa kategorisinin logosu gönderilir.
    """
    def get(self, request, channel_slug, category_slug=None, *args, **kwargs):
        is_authed, err_msg = authenticate_request(request, required_type='read')
        if not is_authed:
            return HttpResponse(
                f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><error><code>401</code><message>{xml_escape(err_msg)}</message></error>",
                content_type='application/xml; charset=utf-8',
                status=401
            )

        clean_slug = normalize_channel_slug(channel_slug)
        channel = Channel.objects.select_related('category').filter(slug=clean_slug).first()

        if not channel:
            return HttpResponse(
                f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><error><code>404</code><message>'{xml_escape(channel_slug)}' adlı kanal/kaynak bulunamadı.</message></error>",
                content_type='application/xml; charset=utf-8',
                status=404
            )

        # URL'de kategori belirtilmişse ve kanalın henüz kategorisi yoksa bağla
        if category_slug:
            clean_cat_slug = normalize_channel_slug(category_slug)
            if clean_cat_slug and channel.category is None:
                cat_obj, _ = Category.objects.get_or_create(
                    slug=clean_cat_slug,
                    defaults={'name': clean_cat_slug.replace('-', ' ').title()}
                )
                channel.category = cat_obj
                channel.save(update_fields=['category', 'updated_at'])

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
        category = Category.objects.filter(slug=clean_slug).first()
        if not category:
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


@method_decorator(csrf_exempt, name='dispatch')
class UniversalFeedOrIngestView(View):
    """
    /<category_slug>/<channel_slug> için hibrit evrensel uç:
    - POST: Ingest / Writer API (Öğeyi kaydeder, kategori ve kanalı otomatik açar)
    - GET: Reader RSS Feed (FreshRSS vb. için standart RSS 2.0 XML çıktısı üretir)
    - HEAD: RSS Feed başlıkları
    """
    def post(self, request, category_slug, channel_slug, *args, **kwargs):
        return FlowIngestView.as_view()(request, category_slug=category_slug, channel_slug=channel_slug, *args, **kwargs)

    def get(self, request, category_slug, channel_slug, *args, **kwargs):
        return ChannelRssFeedView.as_view()(request, category_slug=category_slug, channel_slug=channel_slug, *args, **kwargs)

    def head(self, request, category_slug, channel_slug, *args, **kwargs):
        return ChannelRssFeedView.as_view()(request, category_slug=category_slug, channel_slug=channel_slug, *args, **kwargs)

    def options(self, request, *args, **kwargs):
        response = HttpResponse(status=200)
        response['Allow'] = 'GET, POST, HEAD, OPTIONS'
        return response
