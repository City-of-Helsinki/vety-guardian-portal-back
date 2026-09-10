from rest_framework import generics

from .models.application import PreschoolApplication
from .serializers import PreschoolApplicationSerializer


class PreschoolApplicationCreateView(generics.CreateAPIView):
    """
    POST /preschool-application-form/

    Tallenna uusi hakemus.
    """

    queryset = PreschoolApplication.objects.all()
    serializer_class = PreschoolApplicationSerializer


class PreschoolApplicationRetrieveView(generics.RetrieveAPIView):
    """
    GET /preschool-application-form/<uuid:uuid>/

    Hae hakemus sen uuid:lla.
    """

    queryset = PreschoolApplication.objects.all()
    serializer_class = PreschoolApplicationSerializer
    lookup_field = "id"
    lookup_url_kwarg = "uuid"
