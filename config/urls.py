from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return JsonResponse({'status': 'ok', 'database': 'ok'}, status=200)
    except Exception as e:
        return JsonResponse({'status': 'error', 'database': str(e)}, status=503)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('health', health_check, name='health_check_no_slash'),
    path('', include('feeds.urls')),
]
