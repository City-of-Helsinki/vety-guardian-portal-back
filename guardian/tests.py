import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import CustomUser
from vtj.models import Dependant, Guardian

from .models.application import ApplicationStatus, PreschoolApplication

GUARDIAN_SSN = "010170-999X"

VALID_SUBMISSION = {
    "status": "submitted",
    "kieli": "fi",
    "hakenutEnsisijaisestiYksityiseen": False,
    "taydentavaVarhaiskasvatus": False,
    "h1Sahkoposti": "huoltaja@example.com",
}


def create_user(ssn: str = "") -> CustomUser:
    return CustomUser.objects.create(uuid=uuid.uuid4(), national_identification_number=ssn, helsinki_profile_id=uuid.uuid4() if ssn else None)


class PreschoolApplicationApiTests(APITestCase):
    def setUp(self):
        guardian = Guardian.objects.create(ssn=GUARDIAN_SSN)
        self.dependant = Dependant.objects.create(ssn="010118-9998")
        self.dependant.guardians.add(guardian)
        self.client.force_authenticate(create_user(GUARDIAN_SSN))

    def create_draft(self) -> str:
        return str(PreschoolApplication.objects.create(dependant=self.dependant, h1_henkilotunnus=GUARDIAN_SSN).pk)

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

    def test_unauthenticated_is_rejected(self):
        application_id = self.create_draft()
        self.client.force_authenticate(None)
        response = self.client.get(self.detail_url(application_id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_verified_identity_is_rejected(self):
        application_id = self.create_draft()
        self.client.force_authenticate(create_user())
        response = self.client.get(self.detail_url(application_id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_guardians_application_is_not_found(self):
        application_id = self.create_draft()
        self.client.force_authenticate(create_user("010101-0101"))
        response = self.client.get(self.detail_url(application_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_for_dependant_uses_logged_in_guardian(self):
        url = reverse("preschool-application-for-dependant", kwargs={"dependant_id": self.dependant.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())

        self.client.force_authenticate(create_user("010101-0101"))
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_for_dependant_assigns_guardian_slots(self):
        other_ssn = "020270-998W"
        self.dependant.guardians.add(Guardian.objects.create(ssn=other_ssn))
        url = reverse("preschool-application-for-dependant", kwargs={"dependant_id": self.dependant.pk})

        # The guardian who opens the application first is h1.
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        self.assertEqual(response.data["h1_henkilotunnus"], GUARDIAN_SSN)
        self.assertEqual(response.data["h2_henkilotunnus"], other_ssn)
        self.assertEqual(response.data["current_guardian"], "h1")

        self.client.force_authenticate(create_user(other_ssn))
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        self.assertEqual(response.data["current_guardian"], "h2")
        response = self.client.get(self.detail_url(response.data["id"]))
        self.assertEqual(response.data["current_guardian"], "h2")

    def create_two_guardian_application(self, **fields):
        other_ssn = "020270-9985"
        self.dependant.guardians.add(Guardian.objects.create(ssn=other_ssn))
        application = PreschoolApplication.objects.create(dependant=self.dependant, h1_henkilotunnus=GUARDIAN_SSN, h2_henkilotunnus=other_ssn, **fields)
        return application, other_ssn

    def test_guardian_can_edit_other_guardians_unsaved_contact_details(self):
        application, _ = self.create_two_guardian_application()

        body = {"status": "draft", "h1Sahkoposti": "h1@example.com", "h2Sahkoposti": "h2@example.com", "h2Puhelinnumero": "0402222222"}
        response = self.client.put(self.detail_url(str(application.pk)), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())

        application.refresh_from_db()
        self.assertEqual(application.h2_sahkoposti, "h2@example.com")
        self.assertEqual(application.h2_puhelinnumero, "0402222222")
        # h1 saved their own details, h2's were entered by h1.
        self.assertTrue(application.h1_yhteystiedot_tallennettu)
        self.assertFalse(application.h2_yhteystiedot_tallennettu)

    def test_other_guardian_can_update_details_entered_for_them(self):
        application, other_ssn = self.create_two_guardian_application(h2_sahkoposti="h2@example.com")
        self.client.force_authenticate(create_user(other_ssn))

        body = {"status": "draft", "h2Sahkoposti": "own@example.com"}
        response = self.client.put(self.detail_url(str(application.pk)), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        self.assertTrue(response.data["h2_yhteystiedot_tallennettu"])

        application.refresh_from_db()
        self.assertEqual(application.h2_sahkoposti, "own@example.com")

    def test_guardian_cannot_edit_other_guardians_saved_contact_details(self):
        application, other_ssn = self.create_two_guardian_application(h1_sahkoposti="h1@example.com", h1_yhteystiedot_tallennettu=True)
        self.client.force_authenticate(create_user(other_ssn))

        body = {"status": "draft", "h1Sahkoposti": "changed@example.com", "h1Puhelinnumero": "0401111111"}
        response = self.client.put(self.detail_url(str(application.pk)), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())

        application.refresh_from_db()
        self.assertEqual(application.h1_sahkoposti, "h1@example.com")
        self.assertEqual(application.h1_puhelinnumero, "")
