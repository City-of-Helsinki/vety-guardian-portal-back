import uuid

from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from vtj.models import Dependant, Guardian
from vtj.serializers import ErrorResponseSerializer
from vtj.views import SSN_PARAMETER

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


class PreschoolApplicationForDependantView(APIView):
    """
    POST /preschool-application-form/for-dependant/<uuid:dependant_id>/?ssn=<guardian_ssn>

    Returns the dependant's existing application (200), or creates a new draft (201)
    prefilled with the child's and guardians' VTJ data.
    Refused (403) when the family has an active Turvakielto.
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dependant_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="Database id (UUID) of the Dependant the application is for.",
            ),
            SSN_PARAMETER,
        ],
        request=None,
        responses={
            200: PreschoolApplicationSerializer,
            201: PreschoolApplicationSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request, dependant_id: uuid.UUID) -> Response:
        # TODO: once authentication exists, take the guardian from the logged-in user instead of `ssn`.
        ssn = request.query_params.get("ssn")
        if not ssn:
            return Response({"error": "Missing required query parameter(s): ssn"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            guardian = Guardian.objects.get(ssn=ssn)
        except Guardian.DoesNotExist:
            return Response({"error": "No such guardian"}, status=status.HTTP_404_NOT_FOUND)

        try:
            dependant = Dependant.objects.get(pk=dependant_id)
        except Dependant.DoesNotExist:
            return Response({"error": "No such dependant"}, status=status.HTTP_404_NOT_FOUND)

        guardians = list(dependant.guardians.all())
        if guardian not in guardians:
            return Response({"error": "Not a guardian of this dependant"}, status=status.HTTP_403_FORBIDDEN)

        if dependant.address_protected or any(g.address_protected for g in guardians):
            return Response({"error": "Turvakielto"}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            # Lock the dependant so concurrent requests can't create two drafts.
            Dependant.objects.select_for_update().get(pk=dependant.pk)
            application = PreschoolApplication.objects.filter(dependant=dependant).order_by("-created_at").first()
            if application is not None:
                # Returns the dependant's existing application (200)
                return Response(PreschoolApplicationSerializer(application).data, status=status.HTTP_200_OK)

            # Creates a new draft application (201)
            other_guardian = next((g for g in guardians if g.pk != guardian.pk), None)
            application = PreschoolApplication.objects.create(
                dependant=dependant,
                nimi=dependant.full_name,
                henkilotunnus=dependant.ssn,
                syntymavuosi=dependant.date_of_birth.year if dependant.date_of_birth else None,
                karttaosoite=dependant.format_address(),
                h1_nimi=guardian.full_name,
                h1_osoite=guardian.format_address(),
                h2_nimi=other_guardian.full_name if other_guardian else "",
                h2_osoite=other_guardian.format_address() if other_guardian else "",
            )

        return Response(PreschoolApplicationSerializer(application).data, status=status.HTTP_201_CREATED)
