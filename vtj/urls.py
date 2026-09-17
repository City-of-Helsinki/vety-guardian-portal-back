from django.urls import path

from . import views

app_name = "vtj"

urlpatterns = [
    path("is_protected_family/", views.IsProtectedFamilyView.as_view(), name="is_protected_family"),
    path("dependants/", views.DependantsView.as_view(), name="dependants"),
    path("guardians/<uuid:dependant_id>/", views.GuardiansView.as_view(), name="guardians"),
]
