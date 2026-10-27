from django.urls import path

from .views import PreschoolApplicationCreateView, PreschoolApplicationDetailView, PreschoolApplicationForDependantView, PreschoolApplicationPdfView

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
    # GET -> lataa lähetetty hakemus PDF:nä
    path(
        "preschool-application-form/<uuid:uuid>/pdf/",
        PreschoolApplicationPdfView.as_view(),
        name="preschool-application-pdf",
    ),
    # POST -> hae lapsen olemassa oleva hakemus tai luo uusi (VTJ-tiedoilla esitäytetty draft)
    path(
        "preschool-application-form/for-dependant/<uuid:dependant_id>/",
        PreschoolApplicationForDependantView.as_view(),
        name="preschool-application-for-dependant",
    ),
]
