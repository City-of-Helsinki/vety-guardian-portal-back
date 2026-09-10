from django.urls import path

from .views import PreschoolApplicationCreateView, PreschoolApplicationRetrieveView

urlpatterns = [
    # POST -> tallenna uusi hakemus
    path(
        "preschool-application-form/",
        PreschoolApplicationCreateView.as_view(),
        name="preschool-application-create",
    ),
    # GET -> hae hakemus uuid:lla
    path(
        "preschool-application-form/<uuid:uuid>/",
        PreschoolApplicationRetrieveView.as_view(),
        name="preschool-application-detail",
    ),
]
