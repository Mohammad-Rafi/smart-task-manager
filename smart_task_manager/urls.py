"""
Smart Task Manager - URL Configuration
Root URL router with API versioning and app routing.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tasks.urls')),
    path('api/v1/', include('tasks.api.urls')),
    path('favicon.ico', RedirectView.as_view(url='/static/tasks/images/favicon.ico')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
