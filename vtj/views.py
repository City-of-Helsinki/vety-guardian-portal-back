"""
HTTP endpoints exposing VTJ dependant/guardian data.

The guardian is always the logged-in user: their henkilötunnus comes from
Helsinki-profiili (see authentication/views.py), never from the request.
"""

from __future__ import annotations

import logging

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import HasVerifiedIdentity
from core.audit import Message, Operation, Role, TargetType, audit

from .exceptions import VTJAuthenticationError, VTJConnectionError, VTJError, VTJResponseError
from .models import Guardian
from .serializers import (
    DependantSerializer,
    DependantsResponseSerializer,
    ErrorResponseSerializer,
    IsProtectedFamilyResponseSerializer,
)
from .sync import fetch_family, save_family

logger = logging.getLogger(__name__)


def _guardian_ssn(request: Request) -> str:
    return request.user.national_identification_number  # pyright: ignore[reportAttributeAccessIssue]


def _end_user(request: Request) -> str:
    """
    VTJ 'Loppukayttaja': the natural person the query is made on behalf of, for VTJ's audit trail.

    The user's Helsinki-profiili id, as specified for the City's Palveluväylä integrations:
    "Loppukayttaja: identifier for the end user, if available (e.g. ID from Helsinki profile)"
    https://helsinkisolutionoffice.atlassian.net/wiki/spaces/platta/pages/7610695829/Suomi.fi-palveluv+yl+integrations

    Stored by POST /auth/identity/ (myProfile.id); HasVerifiedIdentity guarantees it is set.
    """
    return str(request.user.helsinki_profile_id)  # pyright: ignore[reportAttributeAccessIssue]


# VTJ Paluukoodi for "person not found".
VTJ_PERSON_NOT_FOUND = "0001"


def _vtj_error_response(exc: VTJError) -> Response:
    """`code` is what the frontend translates; `error` is for developers."""
    logger.error(f"VTJ error: {exc!s}")
    if isinstance(exc, VTJAuthenticationError):
        return Response({"error": "VTJ authentication failed", "code": "vtj_unavailable"}, status=502)
    if isinstance(exc, VTJConnectionError):
        return Response({"error": "VTJ connection failed, try again later", "code": "vtj_unavailable"}, status=503)
    if isinstance(exc, VTJResponseError) and exc.return_code == VTJ_PERSON_NOT_FOUND:
        return Response({"error": "Person not found in VTJ", "code": "vtj_person_not_found"}, status=404)
    return Response({"error": str(exc), "code": "vtj_error"}, status=502)


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
            404: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
            503: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        try:
            family = fetch_family(_guardian_ssn(request), end_user=_end_user(request))
        except VTJError as exc:
            return _vtj_error_response(exc)

        with transaction.atomic():
            saved = save_family(family)
            audit(
                request,
                Operation.UPDATE,
                Message.GUARDIANS_SAVED_FROM_VTJ,
                role=Role.USER,
                target_type=TargetType.GUARDIAN,
                target_ids=[guardian.pk for guardian in saved.guardians],
            )
            if saved.dependants:
                audit(
                    request,
                    Operation.UPDATE,
                    Message.DEPENDANTS_SAVED_FROM_VTJ,
                    role=Role.USER,
                    target_type=TargetType.DEPENDANT,
                    target_ids=[dependant.pk for dependant in saved.dependants],
                )

        return Response({"is_protected_family": family.is_protected_family})


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

        dependants = list(guardian.dependants.all())
        # Before returning the data, so that a failed audit write fails the request.
        audit(
            request,
            Operation.READ,
            Message.DEPENDANTS_LISTED,
            role=Role.USER,
            target_type=TargetType.DEPENDANT,
            target_ids=[dependant.pk for dependant in dependants],
        )
        return Response({"dependants": DependantSerializer(dependants, many=True).data})
