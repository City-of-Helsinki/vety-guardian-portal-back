from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models.application import ApplicationStatus, PreschoolApplication

VALID_SUBMISSION = {
    "status": "submitted",
    "kieli": "fi",
    "hakenutEnsisijaisestiYksityiseen": False,
    "taydentavaVarhaiskasvatus": False,
    "h1Sahkoposti": "huoltaja@example.com",
}


class PreschoolApplicationApiTests(APITestCase):
    def create_draft(self) -> str:
        response = self.client.post(reverse("preschool-application-create"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data["id"]

    def detail_url(self, application_id: str) -> str:
        return reverse("preschool-application-detail", kwargs={"uuid": application_id})

    def test_create_empty_draft(self):
        response = self.client.post(reverse("preschool-application-create"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "draft")

    def test_create_submitted_is_rejected(self):
        response = self.client.post(reverse("preschool-application-create"), {"status": "submitted"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_put_draft_with_nulls(self):
        application_id = self.create_draft()
        body = {
            "status": "draft",
            "kieli": None,
            "hoidonTarve": None,
            "h1Sahkoposti": None,
            "taydentavaVarhaiskasvatus": None,
            "taydentavaVarhaiskasvatusAloitus": None,
            "arkipoissaolotLkm": None,
        }
        response = self.client.put(self.detail_url(application_id), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())

        application = PreschoolApplication.objects.get(pk=application_id)
        self.assertEqual(application.status, ApplicationStatus.DRAFT)
        self.assertEqual(application.kieli, "")
        self.assertEqual(application.h1_sahkoposti, "")
        self.assertIsNone(application.taydentava_varhaiskasvatus)

    def test_submit_missing_required_fields(self):
        application_id = self.create_draft()
        body = {"status": "submitted", "taydentavaVarhaiskasvatus": True}
        response = self.client.put(self.detail_url(application_id), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in [
            "kieli",
            "hakenutEnsisijaisestiYksityiseen",
            "h1Sahkoposti",
            "taydentavaVarhaiskasvatusAloitus",
            "hoidonTarve",
            "palvelunTarve",
            "arkipoissaolotLkm",
        ]:
            self.assertIn(field, response.json())
        self.assertEqual(PreschoolApplication.objects.get(pk=application_id).status, ApplicationStatus.DRAFT)

    def test_submit_valid(self):
        application_id = self.create_draft()
        response = self.client.put(self.detail_url(application_id), VALID_SUBMISSION, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        self.assertEqual(response.data["status"], "submitted")
        self.assertIsNotNone(response.json()["submittedAt"])

    def test_submitted_application_is_locked(self):
        application_id = self.create_draft()
        self.client.put(self.detail_url(application_id), VALID_SUBMISSION, format="json")

        response = self.client.put(self.detail_url(application_id), {**VALID_SUBMISSION, "kieli": "sv"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PreschoolApplication.objects.get(pk=application_id).kieli, "fi")

    def test_patch_not_allowed(self):
        application_id = self.create_draft()
        response = self.client.patch(self.detail_url(application_id), {"kieli": "sv"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
