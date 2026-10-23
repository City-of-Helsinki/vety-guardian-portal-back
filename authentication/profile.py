"""
Reads the logged-in user's verified personal information from the Helsinki-profiili GraphQL API.
https://github.com/City-of-Helsinki/open-city-profile

The frontend fetches a profile API token (audience HELSINKI_PROFILE_API_AUDIENCE) with the HDS login
module's apiTokensClient and sends it to /auth/identity/. The token is the user's own, so the API returns
only their own profile.
"""

from __future__ import annotations

import base64
import binascii
import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from helusers.jwt import JWT, ValidationError
from helusers.oidc import get_keys

logger = logging.getLogger("vety-guardian-portal-back")

MY_PROFILE_QUERY = """
query {
  myProfile {
    id
    verifiedPersonalInformation {
      firstName
      lastName
      nationalIdentificationNumber
    }
    primaryEmail {
      email
    }
    primaryPhone {
      phone
    }
  }
}
"""


class ProfileError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedPersonalInformation:
    profile_id: str
    first_name: str
    last_name: str
    national_identification_number: str
    email: str
    phone: str


def _profile_uuid(global_id: str) -> str:
    """`myProfile.id` is a Relay global ID: base64 of "ProfileNode:<profile uuid>". Returns the uuid."""
    try:
        type_name, _, raw_id = base64.b64decode(global_id, validate=True).decode().partition(":")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ProfileError(f"Unexpected Helsinki-profiili id: {global_id!r}") from exc
    if type_name != "ProfileNode" or not raw_id:
        raise ProfileError(f"Unexpected Helsinki-profiili id: {global_id!r}")
    return raw_id


def validate_profile_token(token: str, user_uuid: str) -> None:
    """
    Raises ProfileError unless `token` is a valid profile API token issued to the user `user_uuid`.
    Stops a user from binding someone else's henkilötunnus to their account with another user's token.
    """
    try:
        jwt = JWT(token)
        jwt.validate_issuer()
        jwt.validate(get_keys(jwt.issuer), settings.HELSINKI_PROFILE_API_AUDIENCE)
    except ValidationError as exc:
        raise ProfileError(f"Invalid profile API token: {exc}") from exc
    except Exception as exc:
        raise ProfileError("Invalid profile API token") from exc
    if jwt.claims.get("sub") != user_uuid:
        raise ProfileError("Profile API token belongs to another user")


def get_verified_personal_information(token: str) -> VerifiedPersonalInformation | None:
    """
    Returns the user's Suomi.fi-verified information & contact details, or None if the profile has none
    (the user hasn't authenticated strongly).
    """
    try:
        response = requests.post(
            settings.HELSINKI_PROFILE_API_URL,
            json={"query": MY_PROFILE_QUERY},
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.HELSINKI_PROFILE_API_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProfileError(f"Helsinki-profiili request failed: {exc}") from exc

    if body.get("errors"):
        raise ProfileError(f"Helsinki-profiili returned errors: {body['errors']}")

    profile = (body.get("data") or {}).get("myProfile") or {}
    info = profile.get("verifiedPersonalInformation")
    if not info or not info.get("nationalIdentificationNumber"):
        return None
    if not profile.get("id"):
        raise ProfileError("Helsinki-profiili returned no profile id")
    return VerifiedPersonalInformation(
        profile_id=_profile_uuid(profile["id"]),
        first_name=info.get("firstName") or "",
        last_name=info.get("lastName") or "",
        national_identification_number=info["nationalIdentificationNumber"],
        email=(profile.get("primaryEmail") or {}).get("email") or "",
        phone=(profile.get("primaryPhone") or {}).get("phone") or "",
    )
