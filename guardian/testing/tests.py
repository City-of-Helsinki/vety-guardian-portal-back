import importlib
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse
from rest_framework import status
from rest_framework.test import APITestCase

import core.urls
from guardian.models.application import PreschoolApplication
from guardian.test_data import delete_all_applications, delete_data_for_hetu
from vtj.models import Dependant, Guardian

from .views import API_KEY_HEADER

API_KEY = "test-key"
GUARDIAN_SSN = "010170-999X"
OTHER_GUARDIAN_SSN = "020270-999X"
CHILD_SSN = "010118-9998"
SIBLING_SSN = "020218-9998"
OTHER_CHILD_SSN = "030318-9998"


def create_family_data() -> None:
    """Guardian with two children who both have an application, plus an unrelated family."""
    guardian = Guardian.objects.create(ssn=GUARDIAN_SSN)
    for ssn in (CHILD_SSN, SIBLING_SSN):
        dependant = Dependant.objects.create(ssn=ssn)
        dependant.guardians.add(guardian)
        PreschoolApplication.objects.create(dependant=dependant, henkilotunnus=ssn)

    other_guardian = Guardian.objects.create(ssn=OTHER_GUARDIAN_SSN)
    other_child = Dependant.objects.create(ssn=OTHER_CHILD_SSN)
    other_child.guardians.add(other_guardian)
    PreschoolApplication.objects.create(dependant=other_child, henkilotunnus=OTHER_CHILD_SSN)


def reload_urls(**overrides: object) -> None:
    """
    Rebuilds core/urls.py with the given settings, which are read at import time (e.g. TEST_DATA_API_ENABLED).
    Without overrides, restores the routes for the real settings.
    """
    with override_settings(**overrides):
        importlib.reload(core.urls)
        clear_url_caches()


class DeleteDataForHetuTests(TestCase):
    def setUp(self):
        create_family_data()

    def test_child_hetu_deletes_only_that_child(self):
        counts = delete_data_for_hetu(CHILD_SSN)
        self.assertEqual(counts, {"applications": 1, "dependants": 1, "guardians": 0})
        self.assertFalse(Dependant.objects.filter(ssn=CHILD_SSN).exists())
        self.assertFalse(PreschoolApplication.objects.filter(henkilotunnus=CHILD_SSN).exists())
        self.assertTrue(Dependant.objects.filter(ssn=SIBLING_SSN).exists())
        self.assertTrue(Guardian.objects.filter(ssn=GUARDIAN_SSN).exists())

    def test_guardian_hetu_deletes_guardian_and_all_dependants(self):
        counts = delete_data_for_hetu(GUARDIAN_SSN)
        self.assertEqual(counts, {"applications": 2, "dependants": 2, "guardians": 1})
        self.assertEqual(set(Dependant.objects.values_list("ssn", flat=True)), {OTHER_CHILD_SSN})
        self.assertEqual(set(Guardian.objects.values_list("ssn", flat=True)), {OTHER_GUARDIAN_SSN})
        self.assertEqual(PreschoolApplication.objects.count(), 1)

    def test_application_without_dependant_is_deleted_by_henkilotunnus(self):
        PreschoolApplication.objects.create(henkilotunnus="040418-9998")
        self.assertEqual(delete_data_for_hetu("040418-9998")["applications"], 1)

    def test_empty_hetu_is_rejected(self):
        PreschoolApplication.objects.create()  # blank henkilotunnus
        with self.assertRaises(ValueError):
            delete_data_for_hetu("  ")
        self.assertEqual(PreschoolApplication.objects.count(), 4)

    def test_unknown_hetu_deletes_nothing(self):
        self.assertEqual(delete_data_for_hetu("050518-9998"), {"applications": 0, "dependants": 0, "guardians": 0})

    def test_delete_all_applications_keeps_vtj_records(self):
        self.assertEqual(delete_all_applications(), {"applications": 3})
        self.assertEqual(Dependant.objects.count(), 3)


@override_settings(DEBUG=True)
class DeleteByHetuCommandTests(TestCase):
    def test_deletes_with_yes(self):
        create_family_data()
        call_command("db_delete_by_hetu", GUARDIAN_SSN, "--yes", stdout=StringIO())
        self.assertFalse(Guardian.objects.filter(ssn=GUARDIAN_SSN).exists())


@override_settings(TEST_DATA_API_KEY=API_KEY)
class TestDataApiTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reload_urls(TEST_DATA_API_ENABLED=True)
        cls.addClassCleanup(reload_urls)

    def setUp(self):
        create_family_data()

    def post(self, name: str, data: dict | None = None, key: str | None = API_KEY):
        headers = {API_KEY_HEADER: key} if key is not None else {}
        return self.client.post(reverse(name), data or {}, format="json", headers=headers)

    def test_delete_by_hetu(self):
        response = self.post("test-data-delete", {"hetu": GUARDIAN_SSN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"applications": 2, "dependants": 2, "guardians": 1})

    def test_delete_by_hetu_requires_hetu(self):
        for data in ({}, {"hetu": ""}, {"hetu": "   "}):
            response = self.post("test-data-delete", data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PreschoolApplication.objects.count(), 3)

    def test_delete_all(self):
        response = self.post("test-data-delete-all")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"applications": 3})
        self.assertFalse(PreschoolApplication.objects.exists())

    def test_missing_or_wrong_key_is_rejected(self):
        for key in (None, "", "wrong-key"):
            for name in ("test-data-delete", "test-data-delete-all"):
                response = self.post(name, {"hetu": GUARDIAN_SSN}, key=key)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(PreschoolApplication.objects.count(), 3)

    @override_settings(TEST_DATA_API_KEY="")
    def test_rejected_when_key_not_configured(self):
        response = self.post("test-data-delete-all", key="")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestDataApiRoutingTests(SimpleTestCase):
    """core/urls.py includes the API only when TEST_DATA_API_ENABLED is on. Independent of the flag in .env."""

    def setUp(self):
        self.addCleanup(reload_urls)

    def test_not_routed_when_disabled(self):
        reload_urls(TEST_DATA_API_ENABLED=False)
        with self.assertRaises(NoReverseMatch):
            reverse("test-data-delete")

    def test_routed_when_enabled(self):
        reload_urls(TEST_DATA_API_ENABLED=True)
        self.assertEqual(reverse("test-data-delete"), "/test-data/delete/")
