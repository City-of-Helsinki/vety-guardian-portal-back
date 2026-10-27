import logging
import uuid

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from vtj.serializers import ErrorResponseSerializer

from .models import CustomUser
from .profile import ProfileError, get_verified_personal_information, validate_profile_token
from .serializers import IdentityRequestSerializer, IdentityResponseSerializer

logger = logging.getLogger("vety-guardian-portal-back")


class IdentityView(APIView):
    """
    POST /auth/identity/

    Reads the logged-in user's henkilötunnus from Helsinki-profiili and stores it on the user.
    The frontend calls this after login; the VTJ and application endpoints need it.
    """

    @extend_schema(
        request=IdentityRequestSerializer,
        responses={
            200: IdentityResponseSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = IdentityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token: str = serializer.validated_data["profile_api_token"]
        user: CustomUser = request.user  # pyright: ignore[reportAssignmentType]

        try:
            validate_profile_token(token, str(user.uuid))
        except ProfileError as exc:
            logger.warning(f"Rejected profile API token: {exc!s}")
            return Response({"error": "Invalid profile API token"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            info = get_verified_personal_information(token)
        except ProfileError as exc:
            logger.error(f"Helsinki-profiili error: {exc!s}")
            return Response({"error": "Helsinki-profiili request failed"}, status=status.HTTP_502_BAD_GATEWAY)

        if info is None:
            return Response({"error": "Strong authentication (Suomi.fi) required"}, status=status.HTTP_403_FORBIDDEN)

        profile_id = uuid.UUID(info.profile_id)
        if user.national_identification_number != info.national_identification_number or user.helsinki_profile_id != profile_id:
            user.national_identification_number = info.national_identification_number
            user.helsinki_profile_id = profile_id
            user.save(update_fields=["national_identification_number", "helsinki_profile_id"])

        return Response({"first_name": info.first_name, "last_name": info.last_name, "email": info.email, "phone": info.phone})
