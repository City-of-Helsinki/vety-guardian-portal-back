"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
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

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import healthz, readiness

urlpatterns = [
    # Root responds 200 so the CD status code check passes
    path("", healthz, name="root"),
    # OpenShift probes
    path("healthz", healthz, name="healthz"),
    path("readiness", readiness, name="readiness"),
    # OpenAPI schema
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    # Swagger UI
    path(
        "schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Guardian app (preschool application endpoints)
    path("auth/", include("authentication.urls")),
    path("", include("guardian.urls")),
    path("vtj/", include("vtj.urls")),
    # Helsinki-profiili GDPR API
    path("gdpr-api/", include("helsinki_gdpr.urls")),
]

# Development and testing only, see ADMIN_ENABLED in settings.py
if settings.ADMIN_ENABLED:
    urlpatterns.append(path("admin/", admin.site.urls))

if settings.VTJ_MOCK_ENABLED:
    from vtj.testing.views import henkilon_tunnuskysely

    urlpatterns.append(path("vtj-mock/api/HenkilonTunnuskysely", henkilon_tunnuskysely, name="vtj-mock"))

if settings.TEST_DATA_API_ENABLED:
    urlpatterns.append(path("test-data/", include("guardian.testing.urls")))
