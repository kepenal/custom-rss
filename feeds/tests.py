import json
from django.test import TestCase, Client
from django.urls import reverse
from feeds.models import Category, Channel, FeedItem, VideoItem, ApiKey
from feeds.utils import normalize_channel_slug, generate_api_key

class FeedTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test API keys
        self.write_token, write_hash, write_prefix = generate_api_key(prefix='crss_write')
        self.write_key = ApiKey.objects.create(
            name='Test Write Key',
            key_hash=write_hash,
            key_prefix=write_prefix,
            key_type='write',
            is_active=True,
        )
        
        self.read_token, read_hash, read_prefix = generate_api_key(prefix='crss_read')
        self.read_key = ApiKey.objects.create(
            name='Test Read Key',
            key_hash=read_hash,
            key_prefix=read_prefix,
            key_type='read',
            is_active=True,
        )

    def test_slug_normalization(self):
        cases = [
            ('Evrim Ağacı', 'evrim-agaci'),
            ('  Türkçe Karakterler İle Test 123! ', 'turkce-karakterler-ile-test-123'),
            ('Software & Tech News', 'software-tech-news'),
            ('Yapay Zekâ ve Veri', 'yapay-zeka-ve-veri'),
            ('videodaldassak', 'videodaldassak'),
            ('allahinyo', 'allahinyo'),
        ]
        for raw, expected in cases:
            self.assertEqual(normalize_channel_slug(raw), expected)

    def test_auth_rejection(self):
        # Test missing key on ingest
        res1 = self.client.post(reverse('flow_ingest'), data={}, content_type='application/json')
        self.assertEqual(res1.status_code, 401)

    def test_category_and_icon_hierarchy(self):
        # Test Category creation and icon inheritance
        cat = Category.objects.create(
            name='Bilim & Teknoloji',
            icon_url='https://example.com/cat-icon.png'
        )
        self.assertEqual(cat.slug, 'bilim-teknoloji')

        # Channel without own icon should inherit category icon
        channel = Channel.objects.create(
            name='Evrim Ağacı',
            category=cat
        )
        self.assertEqual(channel.get_effective_icon_url(), 'https://example.com/cat-icon.png')

        # When channel specifies its own icon, it overrides category icon
        channel.icon_url = 'https://example.com/channel-specific-icon.ico'
        channel.save()
        self.assertEqual(channel.get_effective_icon_url(), 'https://example.com/channel-specific-icon.ico')

    def test_universal_slug_ingest_and_feed(self):
        """
        Test /<category_slug>/<channel_slug> endpoint (e.g. /videodaldassak/allahinyo):
        - POST creates category 'videodaldassak' and channel 'allahinyo'
        - GET returns RSS 2.0 XML for that channel
        """
        payload = {
            'video_id': 'vid_allahinyo_01',
            'title': 'Test İçeriği',
            'summary': 'Bu bir test video özetidir.',
            'key_moments': [
                {'time': '01:10', 'seconds': 70, 'text': 'Giriş'},
            ]
        }

        # 1. POST Ingest to /videodaldassak/allahinyo
        res_post = self.client.post(
            '/videodaldassak/allahinyo',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.write_token}',
        )
        self.assertEqual(res_post.status_code, 201)
        data = res_post.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['category'], 'videodaldassak')
        self.assertEqual(data['channel'], 'allahinyo')
        self.assertEqual(data['content_type'], 'video')
        self.assertEqual(data['feed_url'], '/videodaldassak/allahinyo')

        # Verify Database records
        cat = Category.objects.filter(slug='videodaldassak').first()
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, 'Videodaldassak')

        chan = Channel.objects.filter(slug='allahinyo').first()
        self.assertIsNotNone(chan)
        self.assertEqual(chan.category, cat)

        item = FeedItem.objects.filter(item_id='vid_allahinyo_01').first()
        self.assertIsNotNone(item)
        self.assertEqual(item.channel, chan)
        self.assertEqual(item.content_type, 'video')

        # 2. GET RSS feed from /videodaldassak/allahinyo?key=...
        res_get = self.client.get(f'/videodaldassak/allahinyo?key={self.read_token}')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn('application/rss+xml', res_get['Content-Type'])
        xml_str = res_get.content.decode('utf-8')
        self.assertIn('Allahinyo - RSS Feed', xml_str)
        self.assertIn('Test İçeriği', xml_str)
        self.assertIn('https://youtu.be/vid_allahinyo_01?t=70', xml_str)

        # 3. GET Aggregated category feed /category/videodaldassak?key=...
        res_cat = self.client.get(f'/category/videodaldassak?key={self.read_token}')
        self.assertEqual(res_cat.status_code, 200)
        xml_cat = res_cat.content.decode('utf-8')
        self.assertIn('Videodaldassak - Kategori RSS Akışı', xml_cat)
        self.assertIn('Test İçeriği', xml_cat)

    def test_legacy_ingest_auto_assigns_youtube_category(self):
        """
        Test that legacy POST /api/flows without category automatically assigns
        category 'youtube', ensuring categories are never empty.
        """
        payload = {
            'video_id': 'legacy_vid_01',
            'channel': 'Evrim Ağacı',
            'title': 'Eski Format Video',
            'summary': 'Eski API çağrısı testi.',
        }
        res = self.client.post(
            reverse('flow_ingest'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.write_token}',
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data['category'], 'youtube')

        # Check DB
        cat = Category.objects.filter(slug='youtube').first()
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, 'YouTube')

        chan = Channel.objects.filter(slug='evrim-agaci').first()
        self.assertEqual(chan.category, cat)


class AdminViewsTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.admin = User.objects.create_superuser('testadmin', 'admin@example.com', 'password123')
        self.client.force_login(self.admin)
        
        # Create category with and without icon
        self.cat1 = Category.objects.create(name='Bilim', slug='bilim', icon_url='https://example.com/b.png')
        self.cat2 = Category.objects.create(name='Tarih', slug='tarih')
        
        # Create channels: with own icon, with inherited icon, with no icon
        self.ch1 = Channel.objects.create(name='Evrim Ağacı', slug='evrim-agaci', category=self.cat1, icon_url='https://example.com/e.png')
        self.ch2 = Channel.objects.create(name='Popüler Bilim', slug='populer-bilim', category=self.cat1)
        self.ch3 = Channel.objects.create(name='Genel Kanal', slug='genel-kanal')
        
        self.item = FeedItem.objects.create(
            channel=self.ch1,
            item_id='item-01',
            content_type='video',
            title='Test Video',
            url='https://example.com/v',
            published_at='2026-11-12T10:00:00Z',
        )

    def test_admin_changelist_views(self):
        # Ensure all admin list views render without 500
        for model in ['channel', 'category', 'feeditem', 'apikey']:
            res = self.client.get(f'/admin/feeds/{model}/')
            self.assertEqual(res.status_code, 200, f'Admin changelist for {model} failed')

    def test_admin_changeform_views(self):
        # Ensure change forms render without 500
        res_ch = self.client.get(f'/admin/feeds/channel/{self.ch1.id}/change/')
        self.assertEqual(res_ch.status_code, 200)
        res_ch2 = self.client.get(f'/admin/feeds/channel/{self.ch2.id}/change/')
        self.assertEqual(res_ch2.status_code, 200)
        res_ch3 = self.client.get(f'/admin/feeds/channel/{self.ch3.id}/change/')
        self.assertEqual(res_ch3.status_code, 200)
        res_cat = self.client.get(f'/admin/feeds/category/{self.cat1.id}/change/')
        self.assertEqual(res_cat.status_code, 200)
        res_cat2 = self.client.get(f'/admin/feeds/category/{self.cat2.id}/change/')
        self.assertEqual(res_cat2.status_code, 200)
