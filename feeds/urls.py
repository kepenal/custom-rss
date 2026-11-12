from django.urls import path
from .views import (
    FlowIngestView,
    ChannelRssFeedView,
    CategoryRssFeedView,
    UniversalFeedOrIngestView,
)

urlpatterns = [
    # 1. API Ingest Uçları
    path('api/flows', FlowIngestView.as_view(), name='flow_ingest_no_slash'),
    path('api/flows/', FlowIngestView.as_view(), name='flow_ingest'),
    path('api/flows/<str:category_slug>/<str:channel_slug>', FlowIngestView.as_view(), name='flow_ingest_cat_chan_no_slash'),
    path('api/flows/<str:category_slug>/<str:channel_slug>/', FlowIngestView.as_view(), name='flow_ingest_cat_chan'),
    path('api/<str:category_slug>/<str:channel_slug>', FlowIngestView.as_view(), name='api_ingest_cat_chan_no_slash'),
    path('api/<str:category_slug>/<str:channel_slug>/', FlowIngestView.as_view(), name='api_ingest_cat_chan'),

    # 2. Açık Kategori Feed'i (Kategorideki tüm kanalları tek feed'de toplar)
    path('category/<str:category_slug>', CategoryRssFeedView.as_view(), name='category_feed_no_slash'),
    path('category/<str:category_slug>/', CategoryRssFeedView.as_view(), name='category_feed'),
    path('c/<str:category_slug>', CategoryRssFeedView.as_view(), name='category_feed_short_no_slash'),
    path('c/<str:category_slug>/', CategoryRssFeedView.as_view(), name='category_feed_short'),

    # 3. Geriye Dönük Uyumluluk Prefixleri
    path('youtube/<str:channel_slug>', ChannelRssFeedView.as_view(), {'category_slug': 'youtube'}, name='youtube_feed_no_slash'),
    path('youtube/<str:channel_slug>/', ChannelRssFeedView.as_view(), {'category_slug': 'youtube'}, name='youtube_feed'),
    path('channel/<str:channel_slug>', ChannelRssFeedView.as_view(), name='channel_feed_no_slash'),
    path('channel/<str:channel_slug>/', ChannelRssFeedView.as_view(), name='channel_feed'),
    path('source/<str:channel_slug>', ChannelRssFeedView.as_view(), name='source_feed_no_slash'),
    path('source/<str:channel_slug>/', ChannelRssFeedView.as_view(), name='source_feed'),

    # 4. Evrensel Kategori / Kanal Ucu (POST: Ingest, GET: RSS 2.0 XML)
    # Örnek: /videodaldassak/allahinyo
    path('<str:category_slug>/<str:channel_slug>', UniversalFeedOrIngestView.as_view(), name='universal_feed_or_ingest_no_slash'),
    path('<str:category_slug>/<str:channel_slug>/', UniversalFeedOrIngestView.as_view(), name='universal_feed_or_ingest'),
]
