"""
URL configuration for ITadis CRM project
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from itadis_app.views.auth import browser_logout_view

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    path('logout/', browser_logout_view, name='browser-logout'),
    
    # API v1
    path('api/v1/', include('itadis_app.urls')),
    
    # API Documentation (Swagger/OpenAPI)
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
