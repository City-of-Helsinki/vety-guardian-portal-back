"""
HTTP endpoints exposing VTJ dependant/guardian data.

The guardian is always the logged-in user: their henkilötunnus comes from
Helsinki-profiili (see authentication/views.py), never from the request.
"""

from __future__ import annotations

import logging
import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import HasVerifiedIdentity

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


def _guardian_ssn(request: Request) -> str:
    return request.user.national_identification_number  # pyright: ignore[reportAttributeAccessIssue]


def _end_user(request: Request) -> str:
    """VTJ 'Loppukayttaja': the natural person the query is made on behalf of, for VTJ's audit trail."""
    return str(request.user.uuid)  # pyright: ignore[reportAttributeAccessIssue]


def _vtj_error_response(exc: VTJError) -> Response:
    logger.error(f"VTJ error: {exc!s}")
    if isinstance(exc, VTJAuthenticationError):
        return Response({"error": "VTJ authentication failed"}, status=502)
    if isinstance(exc, VTJConnectionError):
        return Response({"error": "VTJ connection failed, try again later"}, status=503)
    return Response({"error": str(exc)}, status=502)


class IsProtectedFamilyView(APIView):
    """
    GET /is_protected_family/
     - fetches and persists the logged-in guardian's whole family
    """

    permission_classes = [HasVerifiedIdentity]

    @extend_schema(
        methods=["GET"],
        responses={
            200: IsProtectedFamilyResponseSerializer,
            502: ErrorResponseSerializer,
            503: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        try:
            is_protected_family = sync_family(_guardian_ssn(request), end_user=_end_user(request))
        except VTJError as exc:
            return _vtj_error_response(exc)

        return Response({"is_protected_family": is_protected_family})


class DependantsView(APIView):
    """
    GET /dependants/
     - the logged-in guardian's own dependants.
    """

    permission_classes = [HasVerifiedIdentity]

    @extend_schema(
        methods=["GET"],
        responses={
            200: DependantsResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        try:
            guardian = Guardian.objects.get(ssn=_guardian_ssn(request))
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

    permission_classes = [HasVerifiedIdentity]

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
        # Only the logged-in guardian's own dependants; others look nonexistent.
        try:
            dependant = Dependant.objects.get(pk=dependant_id, guardians__ssn=_guardian_ssn(request))
        except Dependant.DoesNotExist:
            return Response({"error": "No such dependant"}, status=404)

        return Response(
            {
                "dependant": DependantSerializer(dependant).data,
                "guardians": GuardianSerializer(dependant.guardians.all(), many=True).data,
            }
        )
