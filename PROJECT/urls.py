from django.contrib import admin
from django.urls import include, path

from apps.core.views import service_worker

urlpatterns = [
    path('DDQR9KHA/', admin.site.urls),
    path('sw.js', service_worker, name='service_worker'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('documents/', include('apps.documents.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('api/', include('apps.api.urls')),
    # Uploaded files are deliberately NOT served from MEDIA_URL: they go through
    # the permission-checked views in apps/documents/files.py. If a web server
    # (nginx etc.) is configured to serve /media/ directly, remove that.
]
