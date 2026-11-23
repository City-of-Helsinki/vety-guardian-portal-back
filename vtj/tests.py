import json
import uuid
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings
from django.urls import path
from rest_framework.test import APITestCase

from authentication.models import CustomUser
from vtj import auth, client
from vtj.exceptions import VTJAuthenticationError, VTJConnectionError, VTJResponseError
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

    def test_codemen_family(self):
        _, data = handle_request(PATH, _body("291221ATP00", "HUOLLETTAVA-HUOLTAJAT"))
        guardians = data["VTJHenkiloVastaussanoma"]["Henkilo"]["Huoltaja"]
        self.assertEqual([g["Henkilotunnus"] for g in guardians], ["011190-TP01", "291190-TP10"])
        self.assertEqual(guardians[0]["Syntymaaika"], "19901101")

        _, data = handle_request(PATH, _body("011190-TP01", "HUOLTAJA-HUOLLETTAVAT"))
        dependants = data["VTJHenkiloVastaussanoma"]["Henkilo"]["Huollettava"]
        self.assertEqual([d["Henkilotunnus"] for d in dependants], ["291221ATP00"])
        self.assertEqual(dependants[0]["Syntymaaika"], "20211229")

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
        user = CustomUser.objects.create(uuid=uuid.uuid4(), national_identification_number="210281-9988", helsinki_profile_id=uuid.uuid4())
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


def _response(status: int, body: dict | None = None):
    resp = Mock(spec=requests.Response)
    resp.status_code = status
    resp.ok = status < 400
    resp.json.return_value = body or {}
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


VTJ_OK = {"Paluukoodi": {"koodi": "0000"}, "Henkilo": {}}


@override_settings(
    VTJ_HEL_ENDPOINT="https://vtj.example/api/HenkilonTunnuskysely",
    VTJ_HEL_TOKEN_URL="https://auth.example/token",
    VTJ_HEL_CLIENT_ID="client",
    VTJ_HEL_CLIENT_SECRET="secret",
)
class ClientTokenTests(SimpleTestCase):
    def setUp(self):
        auth.clear_cached_token()
        self.addCleanup(auth.clear_cached_token)

    def _route(self, token_responses: list, api_responses: list):
        def post(url, **kwargs):
            return token_responses.pop(0) if url == "https://auth.example/token" else api_responses.pop(0)

        return patch("requests.post", side_effect=post)

    def test_token_is_requested_with_client_credentials_and_sent_as_bearer(self):

        with self._route([_response(200, {"access_token": "t1", "expires_in": 300})], [_response(200, VTJ_OK)]) as post:
            client.get_basic_info("010101-0101", "user")

        token_call, api_call = post.call_args_list
        self.assertEqual(token_call.kwargs["auth"], ("client", "secret"))
        self.assertEqual(token_call.kwargs["data"], {"grant_type": "client_credentials", "scope": "vtj-api.persons:read"})
        self.assertEqual(api_call.kwargs["headers"]["Authorization"], "Bearer t1")

    def test_token_is_cached_between_calls(self):

        with self._route([_response(200, {"access_token": "t1", "expires_in": 300})], [_response(200, VTJ_OK), _response(200, VTJ_OK)]) as post:
            client.get_basic_info("010101-0101", "user")
            client.get_basic_info("010101-0101", "user")

        self.assertEqual(post.call_count, 3)

    def test_expired_token_is_refreshed(self):

        tokens = [_response(200, {"access_token": "t1", "expires_in": 0}), _response(200, {"access_token": "t2", "expires_in": 300})]
        with self._route(tokens, [_response(200, VTJ_OK), _response(200, VTJ_OK)]) as post:
            client.get_basic_info("010101-0101", "user")
            client.get_basic_info("010101-0101", "user")

        self.assertEqual(post.call_args_list[-1].kwargs["headers"]["Authorization"], "Bearer t2")

    def test_401_retries_once_with_fresh_token(self):

        tokens = [_response(200, {"access_token": "t1", "expires_in": 300}), _response(200, {"access_token": "t2", "expires_in": 300})]
        with self._route(tokens, [_response(401), _response(200, VTJ_OK)]) as post:
            client.get_basic_info("010101-0101", "user")

        self.assertEqual(post.call_args_list[-1].kwargs["headers"]["Authorization"], "Bearer t2")

    def test_persistent_401_raises_authentication_error(self):

        tokens = [_response(200, {"access_token": "t1", "expires_in": 300}), _response(200, {"access_token": "t2", "expires_in": 300})]
        with self._route(tokens, [_response(401), _response(401)]), self.assertRaises(VTJAuthenticationError):
            client.get_basic_info("010101-0101", "user")

    def test_rejected_client_credentials_raise_authentication_error(self):

        with self._route([_response(401)], []), self.assertRaises(VTJAuthenticationError):
            client.get_basic_info("010101-0101", "user")

    @override_settings(VTJ_HEL_CLIENT_ID="")
    def test_no_token_without_client_id(self):

        with self._route([], [_response(200, VTJ_OK)]) as post:
            client.get_basic_info("010101-0101", "user")

        self.assertEqual(post.call_count, 1)
        self.assertNotIn("Authorization", post.call_args.kwargs["headers"])
