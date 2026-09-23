from django.urls import path

from .views import PreschoolApplicationCreateView, PreschoolApplicationDetailView

urlpatterns = [
    # POST -> luo uusi hakemus (draft)
    path(
        "preschool-application-form/",
        PreschoolApplicationCreateView.as_view(),
        name="preschool-application-create",
    ),
    # GET -> hae hakemus uuid:lla, PUT -> päivitä / lähetä hakemus
    path(
        "preschool-application-form/<uuid:uuid>/",
        PreschoolApplicationDetailView.as_view(),
        name="preschool-application-detail",
    ),
]
