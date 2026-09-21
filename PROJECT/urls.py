from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_static

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
    re_path(
        r'^media/(?P<path>.*)$',
        serve_static,
        {'document_root': settings.MEDIA_ROOT},
    ),
]
