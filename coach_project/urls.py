# coach_project/urls.py
from django.contrib import admin
# Import path, include, re_path, TemplateView
from django.urls import path, include, re_path
from django.views.generic import TemplateView
# Import Django auth views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
# Import planning views
from planning import views as planning_views
# Import JWT views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # --- Django Admin ---
    path('admin/', admin.site.urls),

    # --- Coach/SquashSync Specific URLs ---
    # Login/Logout for the main Django site (coaches)
    # *** CORRECTED template_name ***
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    # *******************************
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Coach Dashboard
    path('dashboard/', planning_views.homepage_view, name='homepage'),

    # Other planning app URLs
    path('planning/', include('planning.urls', namespace='planning')),

    # --- API URLs ---
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # For PWA/API login
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/solo/', include('solosync_api.urls')), # SoloSync API

    # --- SoloSync PWA Catch-All (Handles Root) ---
    # This serves React's index.html for the root path ('/') and any other path
    # not matched above (excluding /api/, /admin/, /dashboard/, /planning/).
    # React Router will handle routing like /login, /routines etc. internally.
    # It MUST be the LAST pattern in this list.
    re_path(r'^(?!api/|admin/|dashboard/|planning/).*$', TemplateView.as_view(template_name='index.html'), name='react_app'),

]

# Serving media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

