import base64
import time
import uuid
from importlib.metadata import version
from unittest import mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from helusers.jwt import JWT as HelusersJWT
from jwt.algorithms import RSAAlgorithm
from rest_framework import status
from rest_framework.test import APITestCase

from .models import CustomUser
from .profile import ProfileError

PROFILE_UUID = "6b4ba7a5-7f3e-4a62-9b6d-2a8c1f0e3d11"

PROFILE_RESPONSE = {
    "data": {
        "myProfile": {
            "id": base64.b64encode(f"ProfileNode:{PROFILE_UUID}".encode()).decode(),
            "verifiedPersonalInformation": {
                "firstName": "Parent",
                "lastName": "Example",
                "nationalIdentificationNumber": "010170-999X",
            },
        }
    }
}


def profile_response(body: dict) -> mock.Mock:
    response = mock.Mock()
    response.json.return_value = body
    return response


@mock.patch("authentication.views.validate_profile_token")
@mock.patch("authentication.profile.requests.post")
class IdentityViewTests(APITestCase):
    url = reverse("auth-identity")

    def setUp(self):
        self.user = CustomUser.objects.create(uuid=uuid.uuid4())
        self.client.force_authenticate(self.user)

    def test_stores_national_identification_number(self, post, validate):
        post.return_value = profile_response(PROFILE_RESPONSE)
        response = self.client.post(self.url, {"profileApiToken": "token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        self.assertEqual(response.json(), {"firstName": "Parent", "lastName": "Example"})
        validate.assert_called_once_with("token", str(self.user.uuid))
        self.user.refresh_from_db()
        self.assertEqual(self.user.national_identification_number, "010170-999X")
        self.assertEqual(self.user.helsinki_profile_id, uuid.UUID(PROFILE_UUID))

    def test_rejects_unexpected_profile_id(self, post, validate):
        body = {"data": {"myProfile": {**PROFILE_RESPONSE["data"]["myProfile"], "id": "not-a-global-id"}}}
        post.return_value = profile_response(body)
        response = self.client.post(self.url, {"profileApiToken": "token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.helsinki_profile_id)

    def test_requires_strong_authentication(self, post, validate):
        post.return_value = profile_response({"data": {"myProfile": {"verifiedPersonalInformation": None}}})
        response = self.client.post(self.url, {"profileApiToken": "token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user.refresh_from_db()
        self.assertEqual(self.user.national_identification_number, "")

    def test_rejects_invalid_profile_token(self, post, validate):
        validate.side_effect = ProfileError("Profile API token belongs to another user")
        response = self.client.post(self.url, {"profileApiToken": "token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        post.assert_not_called()

    def test_profile_errors(self, post, validate):
        post.return_value = profile_response({"errors": [{"message": "PERMISSION_DENIED"}]})
        response = self.client.post(self.url, {"profileApiToken": "token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_unauthenticated(self, post, validate):
        self.client.force_authenticate(None)
        response = self.client.post(self.url, {"profileApiToken": "token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


TOKEN_AUDIENCE = "vety-api-test"
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWKS = {"keys": [{**RSAAlgorithm.to_jwk(SIGNING_KEY.public_key(), as_dict=True), "kid": "test"}]}


def signed_token(iat_offset: int) -> str:
    now = int(time.time())
    claims = {"iat": now + iat_offset, "exp": now + 300, "aud": TOKEN_AUDIENCE, "sub": "user"}
    return jwt.encode(claims, SIGNING_KEY, algorithm="RS256", headers={"kid": "test"})


@override_settings(OIDC_API_TOKEN_AUTH_LEEWAY=10)
class TokenClockSkewTests(SimpleTestCase):
    """
    Tunnistus's clock may run slightly ahead of ours, so a fresh token's iat can be in our future.

    Note: HelusersJWT (helusers.jwt.JWT) does not use PyJWT directly. AuthenticationConfig.ready() overwrites
    helusers.jwt.pyjwt with the leeway wrapper from authentication/jwt_leeway.py, so these tests
    exercise that wrapper. The module-level `jwt` in this file is still plain PyJWT.
    """

    def test_accepts_token_issued_slightly_in_the_future(self):
        HelusersJWT(signed_token(iat_offset=1)).validate(JWKS, TOKEN_AUDIENCE)

    def test_rejects_token_issued_beyond_leeway(self):
        with self.assertRaises(jwt.ImmatureSignatureError):
            HelusersJWT(signed_token(iat_offset=60)).validate(JWKS, TOKEN_AUDIENCE)

    @override_settings(OIDC_API_TOKEN_AUTH_LEEWAY=0)
    def test_without_leeway_rejects_token_issued_in_the_future(self):
        with self.assertRaises(jwt.ImmatureSignatureError):
            HelusersJWT(signed_token(iat_offset=1)).validate(JWKS, TOKEN_AUDIENCE)

    def test_reminder_to_recheck_leeway_wrapper_on_helusers_upgrade(self):
        # jwt_leeway.py patches helusers internals. After a helusers upgrade, check whether helusers now has
        # a leeway setting of its own (then remove jwt_leeway.py) and whether it still uses PyJWT the same way,
        # then update the version here. PyJWT upgrades are covered by the behaviour tests above.
        self.assertEqual(
            version("django-helusers"),
            "1.3.0",
            "helusers was upgraded: recheck authentication/jwt_leeway.py (see this test's comment)",
        )
