import logging
import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import HasVerifiedIdentity
from vtj.models import Dependant, Guardian
from vtj.serializers import ErrorResponseSerializer

from .models.application import ApplicationStatus, PreschoolApplication
from .pdf import application_pdf_filename, render_application_pdf
from .serializers import PreschoolApplicationSerializer
from .translations import FALLBACK_LANGUAGE, SUPPORTED_LANGUAGES, TranslationError

logger = logging.getLogger("vety-guardian-portal-back")


def applications_for_guardian(user: AbstractBaseUser | AnonymousUser) -> QuerySet[PreschoolApplication]:
    # Only applications for the logged-in guardian's own dependants; others look nonexistent.
    ssn = user.national_identification_number  # pyright: ignore[reportAttributeAccessIssue]
    return PreschoolApplication.objects.filter(dependant__guardians__ssn=ssn).distinct()


class PreschoolApplicationCreateView(generics.CreateAPIView):
    """
    POST /preschool-application-form/

    Create a new application in "draft" status.
    """

    permission_classes = [HasVerifiedIdentity]
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

    permission_classes = [HasVerifiedIdentity]
    serializer_class = PreschoolApplicationSerializer
    lookup_field = "id"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        return applications_for_guardian(self.request.user)


class PreschoolApplicationPdfView(generics.GenericAPIView):
    """
    GET /preschool-application-form/<uuid:uuid>/pdf/?lang=fi

    Download the submitted application as a PDF, laid out like the Esikatselu step.
    Drafts look nonexistent (404).
    """

    permission_classes = [HasVerifiedIdentity]
    lookup_field = "id"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        return applications_for_guardian(self.request.user).filter(status=ApplicationStatus.SUBMITTED)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="lang",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=list(SUPPORTED_LANGUAGES),
                default=FALLBACK_LANGUAGE,
                description="Language of the PDF texts.",
            ),
        ],
        responses={
            (200, "application/pdf"): OpenApiResponse(response=OpenApiTypes.BINARY, description="The application as a PDF file."),
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            503: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> HttpResponse | Response:
        lang = request.query_params.get("lang", FALLBACK_LANGUAGE)
        if lang not in SUPPORTED_LANGUAGES:
            return Response({"error": "Unsupported language"}, status=status.HTTP_400_BAD_REQUEST)

        application = self.get_object()
        try:
            pdf = render_application_pdf(application, lang)
        except TranslationError as exc:
            logger.error(f"Application PDF failed: {exc!s}")
            return Response({"error": "Translations unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = content_disposition_header(True, application_pdf_filename(application))
        return response


class PreschoolApplicationForDependantView(APIView):
    """
    POST /preschool-application-form/for-dependant/<uuid:dependant_id>/

    Returns the dependant's existing application (200), or creates a new draft (201)
    prefilled with the child's and guardians' VTJ data.
    Refused (403) when the family has an active Turvakielto.
    """

    permission_classes = [HasVerifiedIdentity]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dependant_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="Database id (UUID) of the Dependant the application is for.",
            ),
        ],
        request=None,
        responses={
            200: PreschoolApplicationSerializer,
            201: PreschoolApplicationSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request, dependant_id: uuid.UUID) -> Response:
        ssn = request.user.national_identification_number  # pyright: ignore[reportAttributeAccessIssue]
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
