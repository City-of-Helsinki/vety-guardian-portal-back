"""
HTTP endpoints exposing VTJ dependant/guardian data.



SECURITY - READ BEFORE DEPLOYING ANYWHERE REAL:
there is no authentication or authorization here yet.
Before this goes anywhere near production you MUST add real
authentication, AND authorization on top of it.

Each VTJ request needs to be tied to a real logged-in
user, and that user's right to query the specific person given (and to
have their own identity used as `end_user`) needs to be checked before
calling sync_dependants()/sync_guardians(). A `TODO` marks where that
check belongs in each view below.
"""

from __future__ import annotations

import logging
import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import VTJAuthenticationError, VTJConnectionError, VTJError
from .models import Dependant, Guardian
from .serializers import (
    DependantSerializer,
    DependantsResponseSerializer,
    ErrorResponseSerializer,
    GuardianSerializer,
    GuardiansResponseSerializer,
    IsProtectedFamilyResponseSerializer,
)
from .sync import sync_family

logger = logging.getLogger("vety-guardian-portal-back")

"""
END_USER_PARAMETER = OpenApiParameter(
    name="end_user",
    type=str,
    location=OpenApiParameter.QUERY,
    required=True,
    description=(
        "VTJ 'Loppukayttaja' value - identifier of the real natural person the query is made "
        "on behalf of, required by VTJ itself for the Gateway's own audit/traceability. "
        "Not yet derived from a logged-in user - see this module's SECURITY note."
    ),
)
"""

SSN_PARAMETER = OpenApiParameter(
    name="ssn",
    type=str,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Finnish personal identity code (Henkilotunnus) of the guardian whose family this is.",
)


def _vtj_error_response(exc: VTJError) -> Response:
    logger.error(f"VTJ error: {exc!s}")
    if isinstance(exc, VTJAuthenticationError):
        return Response({"error": "VTJ authentication failed"}, status=502)
    if isinstance(exc, VTJConnectionError):
        return Response({"error": "VTJ connection failed, try again later"}, status=503)
    return Response({"error": str(exc)}, status=502)


class IsProtectedFamilyView(APIView):
    """
    GET /is_protected_family/?ssn=<guardian_ssn>&end_user=<end_user>
     - fetches and persists the guardian's whole family
    """

    # TODO: replace with real permission checks once authentication exists
    # (see the module docstring's SECURITY note) - AllowAny is explicit
    # here as a marker of the current (temporary) state, not an
    # endorsement of it.
    # permission_classes = [AllowAny]

    @extend_schema(
        methods=["GET"],
        # parameters=[SSN_PARAMETER, END_USER_PARAMETER],
        parameters=[SSN_PARAMETER],
        responses={
            200: IsProtectedFamilyResponseSerializer,
            400: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
            503: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        ssn = request.query_params.get("ssn")
        end_user = "TODO: Set real user ID"
        """
        end_user = request.query_params.get("end_user")
        missing = [name for name, value in (("ssn", ssn), ("end_user", end_user)) if not value]
        if missing:
            return Response({"error": f"Missing required query parameter(s): {', '.join(missing)}"}, status=400)
        """
        if not ssn:
            return Response({"error": "Missing required query parameter(s): ssn"}, status=400)

        # TODO: once authentication exists, verify the logged-in user is
        # actually entitled to query `ssn`

        try:
            is_protected_family = sync_family(ssn, end_user=end_user)
        except VTJError as exc:
            return _vtj_error_response(exc)

        return Response({"is_protected_family": is_protected_family})


class DependantsView(APIView):
    """
    GET /dependants/?ssn=<guardian_ssn>
     - that guardian's own dependants.
    """

    # TODO: see IsProtectedFamilyView's identical note above.
    # permission_classes = [AllowAny]

    @extend_schema(
        methods=["GET"],
        parameters=[SSN_PARAMETER],
        responses={
            200: DependantsResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        ssn = request.query_params.get("ssn")
        if not ssn:
            return Response({"error": "Missing required query parameter(s): ssn"}, status=400)

        # TODO: once authentication exists, verify the logged-in user is
        # actually entitled to see this guardian's dependants

        try:
            guardian = Guardian.objects.get(ssn=ssn)
        except Guardian.DoesNotExist:
            return Response({"error": "No such guardian"}, status=404)

        dependants = DependantSerializer(guardian.dependants.all(), many=True).data
        return Response({"dependants": dependants})


class GuardiansView(APIView):
    """
    GET /guardians/<dependant_id>/
     - that dependant's own guardians

    `dependant_id` is the  DATABASE id from a prior /dependants/ response's "id" field
    """

    # TODO: see IsProtectedFamilyView's identical note above.
    # permission_classes = [AllowAny]

    @extend_schema(
        methods=["GET"],
        parameters=[
            OpenApiParameter(
                name="dependant_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description=("Database id (UUID) of the Dependant whose guardians to fetch."),
            ),
        ],
        responses={
            200: GuardiansResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request, dependant_id: uuid.UUID) -> Response:
        # TODO: once authentication exists, verify the logged-in user is
        # actually entitled to see this dependant's guardians.

        try:
            dependant = Dependant.objects.get(pk=dependant_id)
        except Dependant.DoesNotExist:
            return Response({"error": "No such dependant"}, status=404)

        return Response(
            {
                "dependant": DependantSerializer(dependant).data,
                "guardians": GuardianSerializer(dependant.guardians.all(), many=True).data,
            }
        )
