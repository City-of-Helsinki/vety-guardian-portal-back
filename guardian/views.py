from rest_framework import generics

from .models.application import PreschoolApplication
from .serializers import PreschoolApplicationSerializer


class PreschoolApplicationCreateView(generics.CreateAPIView):
    """
    POST /preschool-application-form/

    Create a new application in "draft" status.
    """

    queryset = PreschoolApplication.objects.all()
    serializer_class = PreschoolApplicationSerializer


class PreschoolApplicationDetailView(generics.RetrieveUpdateAPIView):
    """
    GET /preschool-application-form/<uuid:uuid>/
    PUT /preschool-application-form/<uuid:uuid>/

    Retrieve or update the application using its UUID.
    Fields can be null or empty in the "draft".
    When the status is changed to "submitted", then the fields are validated.
    Submitted applications cannot be modified.
    """

    http_method_names = ["get", "put", "head", "options"]

    queryset = PreschoolApplication.objects.all()
    serializer_class = PreschoolApplicationSerializer
    lookup_field = "id"
    lookup_url_kwarg = "uuid"
