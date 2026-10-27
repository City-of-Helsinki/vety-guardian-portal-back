import uuid
from unittest import mock

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import CustomUser
from vtj.models import Dependant, Guardian

from .models.application import ApplicationStatus, PreschoolApplication
from .pdf import render_application_html
from .translations import TranslationError, Translator

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
        return str(PreschoolApplication.objects.create(dependant=self.dependant).pk)

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


TRANSLATIONS = {
    "fi": {
        "title": "Esiopetukseen ilmoittautuminen",
        "language": {"fi": "Suomi"},
        "esikatselu": {
            "title": "Esikatselu ja lähetys",
            "alreadySubmitted": "Ilmoittautuminen on lähetetty",
            "lapsenNimi": "Lapsen nimi",
            "lapsenTiedotText": "Tiedot ovat [DVV:ltä](https://dvv.fi).",
            "muutHuoltajatTitle": "Muut huoltajat",
            "sahkoposti": "Sähköpostiosoite",
        },
        "edit": "Muokkaa",
    },
    "sv": {"esikatselu": {"lapsenNimi": "Barnets namn"}},
    "en": {},
}


def fake_get_translations(lang: str) -> dict:
    return TRANSLATIONS[lang]


@mock.patch("guardian.translations.get_translations", side_effect=fake_get_translations)
class PreschoolApplicationPdfTests(APITestCase):
    def setUp(self):
        guardian = Guardian.objects.create(ssn=GUARDIAN_SSN)
        self.dependant = Dependant.objects.create(ssn="010118-9998")
        self.dependant.guardians.add(guardian)
        self.client.force_authenticate(create_user(GUARDIAN_SSN))

    def create_application(self, **fields) -> PreschoolApplication:
        defaults = {
            "dependant": self.dependant,
            "status": ApplicationStatus.SUBMITTED,
            "nimi": "Testi Lapsi",
            "henkilotunnus": "010118-9998",
            "kieli": "fi",
            "h1_nimi": "Huoltaja Yksi",
            "h1_sahkoposti": "huoltaja@example.com",
        }
        return PreschoolApplication.objects.create(**(defaults | fields))

    def pdf_url(self, application: PreschoolApplication) -> str:
        return reverse("preschool-application-pdf", kwargs={"uuid": application.pk})

    def test_download_submitted(self, _):
        response = self.client.get(self.pdf_url(self.create_application()), {"lang": "sv"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="esiopetusilmoittautuminen.pdf"')
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_draft_is_not_found(self, _):
        application = self.create_application(status=ApplicationStatus.DRAFT)
        response = self.client.get(self.pdf_url(application))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_guardians_application_is_not_found(self, _):
        application = self.create_application()
        self.client.force_authenticate(create_user("010101-0101"))
        response = self.client.get(self.pdf_url(application))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unsupported_language(self, _):
        response = self.client.get(self.pdf_url(self.create_application()), {"lang": "de"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_translations_unavailable(self, get_translations):
        get_translations.side_effect = TranslationError("down")
        response = self.client.get(self.pdf_url(self.create_application()))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_html_content(self, _):
        html = render_application_html(self.create_application(), "fi")
        for text in ["Esiopetukseen ilmoittautuminen", "Testi Lapsi", "010118-9998", "huoltaja@example.com", "Lapsen nimi", "Suomi"]:
            self.assertIn(text, html)
        self.assertIn('<a href="https://dvv.fi">DVV:ltä</a>', html)
        self.assertIn("data:image/svg+xml;base64,", html)
        # Left out of the PDF: the step title, edit links, the "already submitted" notification and the empty muut huoltajat.
        for text in ["Esikatselu ja lähetys", "Muokkaa", "Ilmoittautuminen on lähetetty", "Muut huoltajat"]:
            self.assertNotIn(text, html)

    def test_html_muut_huoltajat(self, _):
        html = render_application_html(self.create_application(h2_nimi="Huoltaja Kaksi"), "fi")
        self.assertIn("Muut huoltajat", html)
        self.assertIn("Huoltaja Kaksi", html)

    def test_html_escapes_values(self, _):
        html = render_application_html(self.create_application(h1_puhelinnumero="<b>040</b>"), "fi")
        self.assertIn("&lt;b&gt;040&lt;/b&gt;", html)

    def test_html_falls_back_to_finnish_then_key(self, _):
        html = render_application_html(self.create_application(), "sv")
        self.assertIn("Barnets namn", html)
        self.assertIn("Sähköpostiosoite", html)
        self.assertIn("esikatselu.henkilotunnus", html)


@override_settings(LOCIZE_CDN_URL="https://locize.example", LOCIZE_PROJECT_ID="project", LOCIZE_VERSION="latest")
class TranslationsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @mock.patch("guardian.translations.requests.get")
    def test_fetches_and_caches(self, get):
        get.return_value.json.return_value = {"esikatselu": {"kieli": "Kieli"}}
        self.assertEqual(Translator("fi")("esikatselu.kieli"), "Kieli")
        Translator("fi")
        get.assert_called_once_with("https://locize.example/project/latest/fi/lomake", timeout=10)

    @mock.patch("guardian.translations.requests.get", side_effect=requests.ConnectionError("down"))
    def test_request_failure(self, _):
        with self.assertRaises(TranslationError):
            Translator("fi")
