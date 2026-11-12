import json
from django.test import TestCase, Client
from django.urls import reverse
from feeds.models import Channel, VideoItem, ApiKey
from feeds.utils import normalize_channel_slug, hash_token

class FeedsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.write_token = 'crss_write_test_secret_token_12345'
        self.read_token = 'crss_read_test_secret_token_67890'
        
        ApiKey.objects.create(
            name='Test n8n Write Key',
            key_hash=hash_token(self.write_token),
            key_prefix=self.write_token[:8],
            key_type='write',
            is_active=True,
        )
        
        ApiKey.objects.create(
            name='Test RSS Reader Key',
            key_hash=hash_token(self.read_token),
            key_prefix=self.read_token[:8],
            key_type='read',
            is_active=True,
        )

    def test_slug_normalization(self):
        cases = [
            ('Barış Özcan', 'baris-ozcan'),
            ('  Türkçe Karakterler İle Test 123! ', 'turkce-karakterler-ile-test-123'),
            ('Software & Tech News', 'software-tech-news'),
        ]
        for raw, expected in cases:
            self.assertEqual(normalize_channel_slug(raw), expected)

    def test_flow_ingest_auth_failure(self):
        response = self.client.post(
            reverse('flow_ingest'),
            data=json.dumps({'video_id': 'abc'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    def test_flow_ingest_success_and_idempotency(self):
        payload = {
            'channel': 'Barış Özcan',
            'channel_url': 'https://www.youtube.com/@BarisOzcan',
            'video_id': 'vid_test_001',
            'title': 'Evrenin Sonu Nasıl Olacak?',
            'summary': 'Bu videoda kozmolojik modeller ve evrenin olası son senaryoları ele alınıyor.',
            'key_moments': [
                {'time': '00:00', 'seconds': 0, 'text': 'Giriş'},
                {'time': '02:45', 'seconds': 165, 'text': 'Büyük Donma Teorisi'},
            ]
        }
        
        # 1. Create with Bearer token
        response1 = self.client.post(
            reverse('flow_ingest'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.write_token}',
        )
        self.assertEqual(response1.status_code, 201)
        res1_json = response1.json()
        self.assertEqual(res1_json['action'], 'created')
        self.assertEqual(res1_json['channel'], 'baris-ozcan')
        
        # Check DB
        self.assertEqual(Channel.objects.count(), 1)
        self.assertEqual(VideoItem.objects.count(), 1)
        video = VideoItem.objects.get(video_id='vid_test_001')
        self.assertEqual(video.title, 'Evrenin Sonu Nasıl Olacak?')
        self.assertEqual(len(video.key_moments), 2)
        
        # 2. Update with X-API-Key header (Idempotent update)
        payload['title'] = 'Evrenin Sonu (Güncellendi)'
        response2 = self.client.post(
            reverse('flow_ingest'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY=self.write_token,
        )
        self.assertEqual(response2.status_code, 200)
        res2_json = response2.json()
        self.assertEqual(res2_json['action'], 'updated')
        
        # Count remains 1
        self.assertEqual(Channel.objects.count(), 1)
        self.assertEqual(VideoItem.objects.count(), 1)
        video.refresh_from_db()
        self.assertEqual(video.title, 'Evrenin Sonu (Güncellendi)')

    def test_rss_feed_output(self):
        # Ingest a video first
        channel = Channel.objects.create(name='Bilim Kanalı', slug='bilim-kanali')
        VideoItem.objects.create(
            channel=channel,
            video_id='sci_01',
            title='Kuantum Fiziği Nedir?',
            url='https://www.youtube.com/watch?v=sci_01',
            published_at='2026-11-12T12:00:00+00:00',
            summary='Kuantum mekaniği ve süperpozisyon ilkeleri.',
            key_moments=[{'time': '01:30', 'seconds': 90, 'text': 'Dalga Parçacık İkiliği'}]
        )
        
        # Unauthorized request
        res_unauth = self.client.get(reverse('channel_feed', kwargs={'channel_slug': 'bilim-kanali'}))
        self.assertEqual(res_unauth.status_code, 401)
        
        # Authorized via ?key= param
        res_query = self.client.get(
            reverse('channel_feed', kwargs={'channel_slug': 'bilim-kanali'}),
            {'key': self.read_token}
        )
        self.assertEqual(res_query.status_code, 200)
        self.assertIn('application/rss+xml', res_query['Content-Type'])
        xml_text = res_query.content.decode('utf-8')
        self.assertIn('<rss version="2.0"', xml_text)
        self.assertIn('<title>Bilim Kanalı - YouTube RSS</title>', xml_text)
        self.assertIn('Kuantum Fiziği Nedir?', xml_text)
        self.assertIn('https://youtu.be/sci_01?t=90', xml_text)
        self.assertIn('Dalga Parçacık İkiliği', xml_text)

    def test_health_check(self):
        res = self.client.get(reverse('health_check'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['status'], 'ok')
