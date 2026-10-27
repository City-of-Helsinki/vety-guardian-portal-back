import uuid
from datetime import UTC, datetime
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
from .pdf import application_pdf_filename, render_application_html
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
        application = self.create_application(submitted_at=datetime(2026, 10, 20, 12, tzinfo=UTC))
        response = self.client.get(self.pdf_url(application), {"lang": "sv"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="esiopetusilmoittautuminen_2026-10-20_Testi_Lapsi.pdf"')
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_filename(self, _):
        # 22:30 UTC is already the next day in Helsinki.
        application = self.create_application(nimi='Äijä  Ö/l*j"y', submitted_at=datetime(2026, 10, 20, 22, 30, tzinfo=UTC))
        self.assertEqual(application_pdf_filename(application), "esiopetusilmoittautuminen_2026-10-21_Äijä_Öljy.pdf")

    def test_filename_non_latin_and_invisible_characters(self, _):
        submitted_at = datetime(2026, 10, 20, 12, tzinfo=UTC)
        cases = {
            "Владимир Петров": "esiopetusilmoittautuminen_2026-10-20_Владимир_Петров.pdf",
            "李 小龙": "esiopetusilmoittautuminen_2026-10-20_李_小龙.pdf",
            # Control characters count as spaces.
            "Testi\tLapsi\n": "esiopetusilmoittautuminen_2026-10-20_Testi_Lapsi.pdf",
            # Format characters (right-to-left override, zero-width joiner, BOM) are dropped.
            "Testi\u202e\u200d\ufeffLapsi": "esiopetusilmoittautuminen_2026-10-20_TestiLapsi.pdf",
        }
        for nimi, expected in cases.items():
            with self.subTest(nimi=nimi):
                application = self.create_application(nimi=nimi, submitted_at=submitted_at)
                self.assertEqual(application_pdf_filename(application), expected)

    def test_filename_max_length(self, _):
        submitted_at = datetime(2026, 10, 20, 12, tzinfo=UTC)
        # "esiopetusilmoittautuminen_2026-10-20_" is 37 characters, leaving 63 for the name.
        filename = application_pdf_filename(self.create_application(nimi="A" * 63 + "B", submitted_at=submitted_at))
        self.assertEqual(filename, "esiopetusilmoittautuminen_2026-10-20_" + "A" * 63 + ".pdf")
        # Counted in characters, not bytes.
        filename = application_pdf_filename(self.create_application(nimi="😀" * 80, submitted_at=submitted_at))
        self.assertEqual(len(filename.removesuffix(".pdf")), 100)
        # No trailing underscore when the cut lands right after one.
        filename = application_pdf_filename(self.create_application(nimi="A" * 62 + " B", submitted_at=submitted_at))
        self.assertEqual(filename, "esiopetusilmoittautuminen_2026-10-20_" + "A" * 62 + ".pdf")

    def test_filename_without_date_and_name(self, _):
        application = self.create_application(nimi="", submitted_at=None)
        self.assertEqual(application_pdf_filename(application), "esiopetusilmoittautuminen.pdf")

    def test_filename_header_with_non_ascii_name(self, _):
        application = self.create_application(nimi="Äijä", submitted_at=datetime(2026, 10, 20, 12, tzinfo=UTC))
        response = self.client.get(self.pdf_url(application))
        self.assertEqual(response["Content-Disposition"], "attachment; filename*=utf-8''esiopetusilmoittautuminen_2026-10-20_%C3%84ij%C3%A4.pdf")

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
        html = render_application_html(self.create_application(h1_henkilotunnus=GUARDIAN_SSN), "fi")
        for text in ["Esiopetukseen ilmoittautuminen", "Testi Lapsi", "010118-9998", "huoltaja@example.com", "Lapsen nimi", "Suomi"]:
            self.assertIn(text, html)
        self.assertInHTML(
            f'<div class="label-value" data-testid="summary-h1-henkilotunnus"><span class="label">esikatselu.henkilotunnus</span><span>{GUARDIAN_SSN}</span></div>',
            html,
        )
        self.assertIn('<a href="https://dvv.fi">DVV:ltä</a>', html)
        self.assertIn("data:image/svg+xml;base64,", html)
        # Left out of the PDF: the step title, edit links, the "already submitted" notification and the empty muut huoltajat.
        for text in ["Esikatselu ja lähetys", "Muokkaa", "Ilmoittautuminen on lähetetty", "Muut huoltajat"]:
            self.assertNotIn(text, html)

    def test_html_muut_huoltajat(self, _):
        html = render_application_html(self.create_application(h2_nimi="Huoltaja Kaksi", h2_henkilotunnus="010101-0101"), "fi")
        self.assertIn("Muut huoltajat", html)
        self.assertIn("Huoltaja Kaksi", html)
        self.assertInHTML(
            '<div class="label-value" data-testid="summary-h2-henkilotunnus"><span class="label">esikatselu.henkilotunnus</span><span>010101-0101</span></div>',
            html,
        )

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
