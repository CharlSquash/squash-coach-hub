# coach_project/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from planning import views as planning_views # Assuming this is your main app's views for homepage
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.views.generic import TemplateView
# from django.views.static import serve as static_serve # Not typically needed if using static() helper for PWA assets in DEBUG
# from pathlib import Path # Not used here after correction
# import os # Not used here after correction

# React app directory (if you build your PWA into a staticfiles dir, Django can serve it via STATIC_URL)
# BASE_DIR = Path(__file__).resolve().parent.parent # settings.py usually has BASE_DIR
# REACT_APP_DIR = settings.BASE_DIR / 'frontend' / 'build' # Example: if your PWA build is in 'frontend/build'

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Auth
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'), # Ensure this is POST only if default

    # Coach dashboard and planning app
    # Assuming 'homepage' is the dashboard. If it's part of 'planning' app, 'planning:homepage' is used in redirects.
    # If your dashboard URL defined here is the one named 'homepage' for the planning app,
    # ensure your planning/urls.py also has a corresponding entry or that this is the primary definition.
    # For clarity, the homepage URL is often defined once. Let's assume planning_views.homepage_view serves it.
    path('', planning_views.homepage_view, name='homepage_root'), # Example: Root of site
    path('dashboard/', planning_views.homepage_view, name='homepage'), # This name is used in planning app redirects

    path('planning/', include('planning.urls', namespace='planning')),

    # API
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Assuming your solosync_api urls are namespaced if include has a namespace argument
    path('api/solosync/', include('solosync_api.urls')), # Or 'solosync_api.urls' without namespace if not defined in solosync_api/urls.py

    # PWA assets - A more common way is to serve these via Django's static files mechanism
    # by putting them in a static directory or configuring STATICFILES_DIRS.
    # The re_path below often handles serving the PWA's index.html, and static files for the PWA
    # (like manifest.json, service-worker.js) are collected by collectstatic and served
    # by the web server in production or Django in DEBUG if configured.

    # For PWA assets, if they are in your STATICFILES_DIRS, the static() helper for STATIC_URL
    # at the bottom (in DEBUG mode) should handle them if the paths are correct.
    # If they are truly outside your normal static flow, your method can work but is less standard.
]

# --- Serve MEDIA files in development (DEBUG=True) ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # If your PWA build files (manifest.json etc.) are not part of your standard static files
    # collected by collectstatic, you might need custom rules or ensure they are in a static dir.
    # If your REACT_APP_DIR is meant to be served as static content, it should ideally be
    # part of settings.STATICFILES_DIRS.
    # The static() helper for STATIC_URL is usually sufficient for all static files.
    # urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) # More common for collectstatic output
    # OR, if STATICFILES_DIRS is set correctly:
    # urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0]) # As you had, if STATICFILES_DIRS[0] is your main static source for PWA too.

# --- Catch-all for React PWA routes (must be last if it's a broad catch-all) ---
# This regex ensures it doesn't catch /api/, /admin/, /media/ (if media is served by Django in DEBUG), etc.
# Ensure MEDIA_URL and STATIC_URL are also excluded if not handled before this.
# The (?!...) is a negative lookahead.
# It's better to have your Django URLs more specific if possible, rather than a broad catch-all.
urlpatterns += [
    re_path(r'^(?!(api/|admin/|media/|static/)).*$', TemplateView.as_view(template_name='index.html'), name='react_app_catch_all'),
]
