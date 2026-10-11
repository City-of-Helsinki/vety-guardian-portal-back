from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasVerifiedIdentity(BasePermission):
    """Logged in, and the henkilötunnus has been read from Helsinki-profiili (POST /auth/identity/)."""

    message = "Identity not verified"

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "national_identification_number", ""))
