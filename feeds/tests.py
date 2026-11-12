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

    def test_flow_ingest_with_category_and_general_content(self):
        payload = {
            'category': 'Yapay Zekâ',
            'source': 'Evrim Ağacı',
            'source_url': 'https://evrimagaci.org',
            'content_type': 'article',
            'item_id': 'art_001',
            'title': 'Evrim Teorisi ve Doğal Seçilim',
            'url': 'https://evrimagaci.org/evrim-teorisi',
            'summary': 'Evrim süreçleri ve adaptasyon mekanizması detaylıca ele alınıyor.',
            'key_moments': [
                {'time': '', 'seconds': 0, 'text': 'Varyasyon ve Mutasyon'},
                {'time': '', 'seconds': 0, 'text': 'Doğal Seçilim ve Üreme Başarısı'}
            ],
            'extra': {'reading_time': '5 min'}
        }
        
        # 1. Post to API with Bearer Token
        res = self.client.post(
            reverse('flow_ingest'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.write_token}',
        )
        self.assertEqual(res.status_code, 201)
        res_data = res.json()
        self.assertEqual(res_data['action'], 'created')
        self.assertEqual(res_data['category'], 'yapay-zeka')
        self.assertEqual(res_data['channel'], 'evrim-agaci')
        self.assertEqual(res_data['content_type'], 'article')

        # Verify DB instances
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Channel.objects.count(), 1)
        self.assertEqual(FeedItem.objects.count(), 1)

        item = FeedItem.objects.first()
        self.assertEqual(item.title, 'Evrim Teorisi ve Doğal Seçilim')
        self.assertEqual(item.channel.category.slug, 'yapay-zeka')
        self.assertEqual(item.extra_data.get('reading_time'), '5 min')

    def test_rss_feed_output_with_icons(self):
        cat = Category.objects.create(name='Bilim', icon_url='https://example.com/bilim.png')
        channel = Channel.objects.create(
            name='Evrim Ağacı',
            slug='evrim-agaci',
            category=cat,
            icon_url='https://example.com/evrim.ico'
        )
        FeedItem.objects.create(
            channel=channel,
            item_id='vid_123',
            content_type='video',
            title='Test Başlığı',
            url='https://www.youtube.com/watch?v=vid_123',
            published_at='2026-11-12T12:00:00Z',
            summary='Harika bir video.',
            key_moments=[{'time': '01:00', 'seconds': 60, 'text': 'Önemli Nokta'}],
        )
        
        # 1. Test Channel Feed: should have channel's own icon
        url_channel = reverse('channel_feed', kwargs={'channel_slug': 'evrim-agaci'}) + f'?key={self.read_token}'
        res_channel = self.client.get(url_channel)
        self.assertEqual(res_channel.status_code, 200)
        xml_ch = res_channel.content.decode('utf-8')
        self.assertIn('<image>', xml_ch)
        self.assertIn('<url>https://example.com/evrim.ico</url>', xml_ch)
        self.assertIn('<atom:icon>https://example.com/evrim.ico</atom:icon>', xml_ch)
        self.assertIn('https://youtu.be/vid_123?t=60', xml_ch)

        # 2. Test Category Feed: should have category's icon and list items in that category
        url_cat = reverse('category_feed', kwargs={'category_slug': 'bilim'}) + f'?key={self.read_token}'
        res_cat = self.client.get(url_cat)
        self.assertEqual(res_cat.status_code, 200)
        xml_cat = res_cat.content.decode('utf-8')
        self.assertIn('<title>Bilim - Kategori RSS Akışı</title>', xml_cat)
        self.assertIn('<url>https://example.com/bilim.png</url>', xml_cat)
        self.assertIn('Test Başlığı', xml_cat)

        # 3. Test Legacy /youtube/<slug> url: works identical to channel feed
        url_yt = reverse('youtube_feed', kwargs={'channel_slug': 'evrim-agaci'}) + f'?key={self.read_token}'
        res_yt = self.client.get(url_yt)
        self.assertEqual(res_yt.status_code, 200)
        self.assertIn('application/rss+xml', res_yt['Content-Type'])


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
