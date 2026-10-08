import uuid

from django.db import models

from .base import BaseModel


class Kieli(models.TextChoices):
    FI = "fi", "Suomi"
    SV = "sv", "Ruotsi"


class HoidonTarve(models.TextChoices):
    PAIVAAIKAINEN_VARHAISKASVATUS = ("paivaaikainen_varhaiskasvatus", "Esiopetus 4 tuntia jonka lisäksi päiväaikainen varhaiskasvatus")
    VUOROHOITO_VARHAISKASVATUS = (
        "vuorohoito_varhaiskasvatus",
        "Esiopetus 4 tuntia arkisin, jonka lisäksi vuorohoidon tarve varhaiskasvatuksessa",
    )


class PalvelunTarve(models.TextChoices):
    ESIOPETUS_4H_1H_VAKA = "esiopetus_4h_1h_vaka", "Esiop +päiväh, yht 5t/pv"
    ESIOPETUS_4H_1_3H_VAKA = "esiopetus_4h_1_3h_vaka", "Esiop+ päiväh, yht 5-7/pv"
    ESIOPETUS_4H_3_4H_VAKA = "esiopetus_4h_3_4h_vaka", "Esiop +päiväh, yht 7-8/pv"
    ESIOPETUS_4H_4_6H_VAKA = "esiopetus_4h_4_6h_vaka", "Esiop +päiväh, yli 7t/pv"

    ESIOPETUS_4H_61_100H_VUOROH = "esiopetus_4h_61_100h_vuoroh", "Esiopetus + Vuorohoito 61-100h/kk"
    ESIOPETUS_4H_101_160H_VUOROH = "esiopetus_4h_101_160h_vuoroh", "Esiopetus + Vuorohoito 101-160h/kk"
    ESIOPETUS_4H_160H_VUOROH = "esiopetus_4h_160h_vuoroh", "Esiopetus + Vuorohoito yli 160h/kk"


class ApplicationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"


class PreschoolApplication(BaseModel):
    """
    Esiopetukseen ilmoittautuminen (preschool application).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Hakemuksen tila ---
    status = models.CharField(max_length=16, choices=ApplicationStatus.choices, default=ApplicationStatus.DRAFT, verbose_name="Tila")
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="Lähetetty")

    # --- Lomake: esiopetukseen / hoitoon liittyvät tiedot ---
    hakenut_ensisijaisesti_yksityiseen = models.BooleanField(
        null=True, blank=True, default=None, verbose_name="Onko hakenut ensisijaisesti yksityiseen päiväkotiin"
    )
    kieli = models.CharField(max_length=2, choices=Kieli.choices, blank=True, verbose_name="Esiopetuksen kieli")
    taydentava_varhaiskasvatus = models.BooleanField(null=True, blank=True, default=None, verbose_name="Tarvitseeko täydentävää varhaiskasvatusta")
    taydentava_varhaiskasvatus_aloitus = models.DateField(
        null=True,
        blank=True,
        verbose_name="Täydentävän varhaiskasvatuksen aloituspäivä",
        help_text="Date in ISO 8601 format (YYYY-MM-DD).",
    )
    hoidon_tarve = models.CharField(max_length=64, choices=HoidonTarve.choices, blank=True, verbose_name="Vuorohoidon tarve")
    palvelun_tarve = models.CharField(max_length=32, choices=PalvelunTarve.choices, blank=True, verbose_name="Laajuus yhteensä")
    arkipoissaolot_lkm = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Arkipoissaolojen lukumäärä")
    erityisen_tuen_tarve = models.BooleanField(null=True, blank=True, default=None, verbose_name="Erityisen tuen tarve")
    laakehoidon_tarve = models.BooleanField(null=True, blank=True, default=None, verbose_name="Lääkehoidon tarve")

    # --- VTJ: lapsen tiedot (väestötietojärjestelmästä haettu) ---
    dependant = models.ForeignKey(
        "vtj.Dependant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name="Lapsi",
    )
    nimi = models.CharField(max_length=255, blank=True, verbose_name="Lapsen nimi")
    henkilotunnus = models.CharField(max_length=11, blank=True, verbose_name="Henkilötunnus")
    karttaosoite = models.CharField(max_length=255, blank=True, verbose_name="Karttaosoite")
    syntymavuosi = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Syntymävuosi")

    # --- Huoltaja 1 ---
    h1_nimi = models.CharField(max_length=255, blank=True, verbose_name="Huoltaja 1 nimi")
    h1_osoite = models.CharField(max_length=255, blank=True, verbose_name="Huoltaja 1 osoite")
    # --- Huoltaja 1 - VTJ heattu ---
    h1_sahkoposti = models.EmailField(blank=True, verbose_name="Huoltaja 1 sähköposti")
    h1_puhelinnumero = models.CharField(max_length=20, blank=True, verbose_name="Huoltaja 1 puhelinnumero")

    # --- Huoltaja 2 (valinnainen) ---
    h2_nimi = models.CharField(max_length=255, blank=True, verbose_name="Huoltaja 2 nimi")
    h2_osoite = models.CharField(max_length=255, blank=True, verbose_name="Huoltaja 2 osoite")
    # --- Huoltaja 2 - VTJ heattu ---
    h2_sahkoposti = models.EmailField(blank=True, verbose_name="Huoltaja 2 sähköposti")
    h2_puhelinnumero = models.CharField(max_length=20, blank=True, verbose_name="Huoltaja 2 puhelinnumero")

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Esiopetushakemus"
        verbose_name_plural = "Esiopetushakemukset"

    def __str__(self):
        return f"Esiopetushakemus {self.id} (created at {self.created_at})"
