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
from .models import Channel, VideoItem
from .utils import normalize_channel_slug

@method_decorator(csrf_exempt, name='dispatch')
class FlowIngestView(View):
    """
    n8n akışlarından gelen video özet ve zaman damgası verilerini alan POST API ucu.
    """
    def post(self, request, *args, **kwargs):
        is_authed, err_msg = authenticate_request(request, required_type='write')
        if not is_authed:
            return JsonResponse({'status': 'error', 'message': err_msg}, status=401)
            
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Geçersiz JSON gövdesi: {str(e)}'}, status=400)
            
        video_id = str(payload.get('video_id', '')).strip()
        title = str(payload.get('title', '')).strip()
        channel_name = str(payload.get('channel') or payload.get('channel_name') or payload.get('channel_title') or '').strip()
        channel_slug = str(payload.get('channel_slug', '')).strip()
        
        if not video_id:
            return JsonResponse({'status': 'error', 'message': "'video_id' zorunludur."}, status=400)
        if not title:
            return JsonResponse({'status': 'error', 'message': "'title' (video başlığı) zorunludur."}, status=400)
        if not channel_name and not channel_slug:
            channel_name = 'Genel Kanal'
            
        target_slug = channel_slug if channel_slug else normalize_channel_slug(channel_name)
        if not target_slug:
            target_slug = 'default'
            
        channel_source_url = str(payload.get('channel_url', '')).strip()
        channel, _ = Channel.objects.get_or_create(
            slug=target_slug,
            defaults={
                'name': channel_name or target_slug,
                'source_url': channel_source_url,
            }
        )
        
        if channel_name and channel.name != channel_name:
            channel.name = channel_name
            if channel_source_url and not channel.source_url:
                channel.source_url = channel_source_url
            channel.save(update_fields=['name', 'source_url', 'updated_at'])
            
        video_url = str(payload.get('url', '')).strip()
        if not video_url:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
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
                time_str = str(item.get('time', '')).strip()
                sec = item.get('seconds', 0)
                text_val = str(item.get('text', '')).strip()
                sanitized_key_moments.append({
                    'time': time_str,
                    'seconds': sec,
                    'text': text_val
                })
                
        video, created = VideoItem.objects.update_or_create(
            video_id=video_id,
            defaults={
                'channel': channel,
                'title': title,
                'url': video_url,
                'published_at': published_at,
                'summary': summary,
                'key_moments': sanitized_key_moments,
            }
        )
        
        return JsonResponse({
            'status': 'ok',
            'action': 'created' if created else 'updated',
            'video_id': video.video_id,
            'channel': channel.slug,
            'title': video.title,
        }, status=201 if created else 200)


class ChannelRssFeedView(View):
    """
    Kanal bazlı zenginleştirilmiş RSS 2.0 XML akışı sunar.
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
            channel = Channel.objects.get(slug=clean_slug)
        except Channel.DoesNotExist:
            return HttpResponse(
                f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><error><code>404</code><message>'{xml_escape(channel_slug)}' adlı kanal bulunamadı.</message></error>",
                content_type='application/xml; charset=utf-8',
                status=404
            )
            
        limit = getattr(settings, 'RSS_FEED_LIMIT', 50)
        videos = channel.videos.all().order_by('-published_at')[:limit]
        
        build_date_str = date_format(timezone.now(), 'r')
        channel_link = channel.source_url or request.build_absolute_uri()
        
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
            '  <channel>',
            f'    <title>{xml_escape(channel.name)} - YouTube RSS</title>',
            f'    <link>{xml_escape(channel_link)}</link>',
            f'    <description>{xml_escape(channel.name)} kanalına ait yapay zekâ özetli ve zaman damgalı RSS feed akışı.</description>',
            '    <language>tr</language>',
            f'    <lastBuildDate>{build_date_str}</lastBuildDate>',
            f'    <atom:link href="{xml_escape(request.build_absolute_uri())}" rel="self" type="application/rss+xml" />',
        ]
        
        for video in videos:
            pub_date_str = date_format(video.published_at, 'r')
            html_parts = []
            if video.summary:
                html_parts.append(f"<h3>Özet</h3><p>{xml_escape(video.summary)}</p>")
            
            if video.key_moments:
                html_parts.append("<h3>Önemli Anlar</h3><ul>")
                for km in video.key_moments:
                    t_label = xml_escape(str(km.get('time', '')))
                    t_sec = km.get('seconds', 0)
                    t_text = xml_escape(str(km.get('text', '')))
                    
                    if t_sec and int(t_sec) > 0:
                        time_url = f"https://youtu.be/{video.video_id}?t={t_sec}"
                    else:
                        time_url = f"https://youtu.be/{video.video_id}"
                    
                    html_parts.append(f"<li><a href=\"{time_url}\"><strong>[{t_label}]</strong></a> {t_text}</li>")
                html_parts.append("</ul>")
                
            html_parts.append(f"<p><a href=\"{xml_escape(video.url)}\">YouTube'da İzle &rarr;</a></p>")
            description_html = "\n".join(html_parts)
            
            xml_lines.append('    <item>')
            xml_lines.append(f'      <title>{xml_escape(video.title)}</title>')
            xml_lines.append(f'      <link>{xml_escape(video.url)}</link>')
            xml_lines.append(f'      <guid isPermaLink="false">{video.video_id}</guid>')
            xml_lines.append(f'      <pubDate>{pub_date_str}</pubDate>')
            xml_lines.append(f'      <description><![CDATA[{description_html}]]></description>')
            xml_lines.append('    </item>')
            
        xml_lines.append('  </channel>')
        xml_lines.append('</rss>')
        
        xml_content = '\n'.join(xml_lines)
        return HttpResponse(xml_content, content_type='application/rss+xml; charset=utf-8')
