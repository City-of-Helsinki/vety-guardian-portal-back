import json
import uuid
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import path
from rest_framework.test import APITestCase

from authentication.models import CustomUser
from vtj.exceptions import VTJConnectionError, VTJResponseError
from vtj.testing.mock_server import NOT_FOUND_SSN, PATH, handle_request
from vtj.testing.views import henkilon_tunnuskysely

MOCK_URL = "/vtj-mock/api/HenkilonTunnuskysely"

urlpatterns = [path(MOCK_URL.lstrip("/"), henkilon_tunnuskysely)]


def _body(ssn: str, sosonimi: str = "PERUSSANOMA 1", end_user: str = "test-user") -> bytes:
    return json.dumps({"Henkilotunnus": ssn, "SoSoNimi": sosonimi, "Loppukayttaja": end_user}).encode()


class MockHandleRequestTests(SimpleTestCase):
    def test_basic_info(self):
        status, data = handle_request(PATH, _body("010170-999X"))
        self.assertEqual(status, 200)
        response = data["VTJHenkiloVastaussanoma"]
        self.assertEqual(response["Paluukoodi"]["koodi"], "0000")
        self.assertEqual(response["Henkilo"]["Henkilotunnus"], "010170-999X")
        self.assertNotIn("Huollettava", response["Henkilo"])

    def test_dependants(self):
        status, data = handle_request(PATH, _body("010170-999X", "HUOLTAJA-HUOLLETTAVAT"))
        self.assertEqual(status, 200)
        self.assertEqual(len(data["VTJHenkiloVastaussanoma"]["Henkilo"]["Huollettava"]), 2)

    def test_guardians_missing_from_fixture_returns_empty_list(self):
        status, data = handle_request(PATH, _body("010101-0101", "HUOLLETTAVA-HUOLTAJAT"))
        self.assertEqual(status, 200)
        self.assertEqual(data["VTJHenkiloVastaussanoma"]["Henkilo"]["Huoltaja"], [])

    def test_not_found(self):
        for ssn in (NOT_FOUND_SSN, "999999-9999"):
            status, data = handle_request(PATH, _body(ssn))
            self.assertEqual(status, 200)
            self.assertEqual(data["VTJHenkiloVastaussanoma"]["Paluukoodi"]["koodi"], "0001")

    def test_missing_end_user(self):
        status, _ = handle_request(PATH, _body("010170-999X", end_user=""))
        self.assertEqual(status, 400)

    def test_unknown_sosonimi(self):
        status, _ = handle_request(PATH, _body("010170-999X", "UNKNOWN"))
        self.assertEqual(status, 400)

    def test_invalid_json(self):
        status, _ = handle_request(PATH, b"not json")
        self.assertEqual(status, 400)

    def test_wrong_path(self):
        status, _ = handle_request("/wrong", _body("010170-999X"))
        self.assertEqual(status, 404)


@override_settings(ROOT_URLCONF=__name__)
class MockViewTests(SimpleTestCase):
    def test_post_returns_mock_response(self):
        response = self.client.post(MOCK_URL, _body("010170-999X", "HUOLTAJA-HUOLLETTAVAT"), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), handle_request(PATH, _body("010170-999X", "HUOLTAJA-HUOLLETTAVAT"))[1])

    def test_error_status_is_passed_through(self):
        response = self.client.post(MOCK_URL, _body("010170-999X", end_user=""), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(MOCK_URL).status_code, 405)


class IsProtectedFamilyErrorTests(APITestCase):
    def setUp(self):
        user = CustomUser.objects.create(uuid=uuid.uuid4(), national_identification_number="210281-9988")
        self.client.force_authenticate(user)

    def get_with_error(self, exc: Exception):
        with patch("vtj.views.sync_family", side_effect=exc):
            return self.client.get("/vtj/is_protected_family/")

    def test_person_not_found(self):
        response = self.get_with_error(VTJResponseError("0001", "Person not found"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "vtj_person_not_found")

    def test_other_return_code(self):
        response = self.get_with_error(VTJResponseError("0002", "Something else"))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "vtj_error")

    def test_connection_error(self):
        response = self.get_with_error(VTJConnectionError("timeout"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "vtj_unavailable")
