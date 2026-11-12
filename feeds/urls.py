from django.urls import path
from .views import FlowIngestView, ChannelRssFeedView

urlpatterns = [
    path('api/flows', FlowIngestView.as_view(), name='flow_ingest_no_slash'),
    path('api/flows/', FlowIngestView.as_view(), name='flow_ingest'),
    path('youtube/<slug:channel_slug>', ChannelRssFeedView.as_view(), name='channel_feed_no_slash'),
    path('youtube/<slug:channel_slug>/', ChannelRssFeedView.as_view(), name='channel_feed'),
]
