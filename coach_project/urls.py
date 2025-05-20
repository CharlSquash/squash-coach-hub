# coach_project/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from planning import views as planning_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.views.generic import TemplateView
from django.views.static import serve as static_serve
from pathlib import Path
import os

# React app directory
BASE_DIR = Path(__file__).resolve().parent.parent
REACT_APP_DIR = BASE_DIR / 'solosync-pwa'

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Auth
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Coach dashboard and planning
    path('dashboard/', planning_views.homepage_view, name='homepage'),
    path('planning/', include('planning.urls', namespace='planning')),

    # API
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/solo/', include('solosync_api.urls')),

    # PWA assets
    path('manifest.json', static_serve, {
        'path': 'build/manifest.json',
        'document_root': REACT_APP_DIR,
    }),
    path('favicon.ico', static_serve, {
        'path': 'build/favicon.ico',
        'document_root': REACT_APP_DIR,
    }),
    path('service-worker.js', static_serve, {
        'path': 'build/service-worker.js',
        'document_root': REACT_APP_DIR,
    }),
    path('solosync-icon-192.png', static_serve, {
        'path': 'build/solosync-icon-192.png',
        'document_root': REACT_APP_DIR,
    }),
    path('solosync-icon-512.png', static_serve, {
        'path': 'build/solosync-icon-512.png',
        'document_root': REACT_APP_DIR,
    }),

    # Catch-all for React routes (must be last)
    re_path(r'^(?!api/|admin/|dashboard/|planning/).*$', TemplateView.as_view(template_name='index.html'), name='react_app'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
