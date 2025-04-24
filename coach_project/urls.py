# coach_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Needed for media files in development
from django.conf.urls.static import static # Needed for media files in development
# Import planning views to point the homepage URL
from planning import views as planning_views

urlpatterns = [
    # Map the root URL ('') to the new homepage_view
    path('', planning_views.homepage_view, name='homepage'),
    # Keep the existing admin and planning app paths
    path('admin/', admin.site.urls),
    path('planning/', include('planning.urls')), # App-specific URLs
]

# --- Add this block for serving media files during development ---
if settings.DEBUG:
    print(f"DEBUG Status Check: {settings.DEBUG}")
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)