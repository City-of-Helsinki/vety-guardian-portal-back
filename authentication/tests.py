import uuid
from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import CustomUser
from .profile import ProfileError

PROFILE_RESPONSE = {
    "data": {
        "myProfile": {
            "verifiedPersonalInformation": {
                "firstName": "Parent",
                "lastName": "Example",
                "nationalIdentificationNumber": "010170-999X",
            }
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
