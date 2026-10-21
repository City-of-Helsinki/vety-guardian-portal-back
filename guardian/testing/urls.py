from django.urls import path

from .views import DeleteAllTestDataView, DeleteTestDataForHetuView

urlpatterns = [
    # POST {"hetu": ...} -> poista hetuun (lapsi tai huoltaja) liittyvät hakemukset ja VTJ-henkilötiedot
    path("delete/", DeleteTestDataForHetuView.as_view(), name="test-data-delete"),
    # POST -> poista kaikki hakemukset (PreschoolApplication)
    path("delete-all/", DeleteAllTestDataView.as_view(), name="test-data-delete-all"),
]
