"""
URL configuration for djangoProject1 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Swagger/OpenAPI documentation setup
schema_view = get_schema_view(
   openapi.Info(
      title="Banking API",
      default_version='v1',
      description="API documentation for Banking operations",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@banking.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   authentication_classes=[],  # Empty list to avoid requiring auth for docs
)

urlpatterns = [
    # Admin site
    path('admin/', admin.site.urls),
    
    # API urls
    path('api/', include('banking.urls')),
    
    # Swagger documentation
    path('api/schema<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Add debug toolbar in development
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
