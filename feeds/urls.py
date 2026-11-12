from django.urls import path
from .views import FlowIngestView, ChannelRssFeedView, CategoryRssFeedView

urlpatterns = [
    # API Ingest (n8n ve harici akışlar)
    path('api/flows', FlowIngestView.as_view(), name='flow_ingest_no_slash'),
    path('api/flows/', FlowIngestView.as_view(), name='flow_ingest'),
    
    # Kanal / Kaynak RSS Akışları
    path('youtube/<slug:channel_slug>', ChannelRssFeedView.as_view(), name='youtube_feed_no_slash'),
    path('youtube/<slug:channel_slug>/', ChannelRssFeedView.as_view(), name='youtube_feed'),
    path('source/<slug:channel_slug>', ChannelRssFeedView.as_view(), name='source_feed_no_slash'),
    path('source/<slug:channel_slug>/', ChannelRssFeedView.as_view(), name='source_feed'),
    path('channel/<slug:channel_slug>', ChannelRssFeedView.as_view(), name='channel_feed_no_slash'),
    path('channel/<slug:channel_slug>/', ChannelRssFeedView.as_view(), name='channel_feed'),
    
    # Kategori RSS Akışları (FreshRSS vb. için tüm kategoriyi tek feed yapar)
    path('category/<slug:category_slug>', CategoryRssFeedView.as_view(), name='category_feed_no_slash'),
    path('category/<slug:category_slug>/', CategoryRssFeedView.as_view(), name='category_feed'),
]
