# coach_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Needed for media files in development
from django.conf.urls.static import static # Needed for media files in development
# Import planning views to point the homepage URL
from planning import views as planning_views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # Map the root URL ('') to the new homepage_view
    path('', planning_views.homepage_view, name='homepage'), # Correctly named homepage

    # Keep the existing admin path
    path('admin/', admin.site.urls),

    # Include planning app URLs under '/planning/' prefix WITH namespace
    # The 'namespace' argument is crucial for {% url 'planning:...' %} tags
    path('planning/', include('planning.urls', namespace='planning')), # <--- ADDED namespace='planning' HERE

    # Add URLs for JWT Token Authentication provided by simplejwt
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

     # Include the URLs from our solosync_api app under the '/api/solo/' prefix
    path('api/solo/', include('solosync_api.urls')),

]

# --- Add this block for serving media files during development ---
if settings.DEBUG:
    # print(f"DEBUG Status Check: {settings.DEBUG}") # You can keep or remove this print statement
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

