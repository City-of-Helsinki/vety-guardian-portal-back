from django.urls import path

from .views import IdentityView

urlpatterns = [
    path("identity/", IdentityView.as_view(), name="auth-identity"),
]
