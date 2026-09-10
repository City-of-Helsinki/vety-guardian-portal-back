from rest_framework import serializers

from .models.application import PreschoolApplication


class PreschoolApplicationSerializer(serializers.ModelSerializer):
    """
    Serializer for PreschoolApplication.
    """

    class Meta:
        model = PreschoolApplication
        fields = [
            "id",
            "created_at",
            "updated_at",
            "hakenut_ensisijaisesti_yksityiseen",
            "kieli",
            "taydentava_varhaiskasvatus",
            "taydentava_varhaiskasvatus_aloitus",
            "hoidon_tarve",
            "palvelun_tarve",
            "arkipoissaolot_lkm",
            "erityisen_tuen_tarve",
            "laakehoidon_tarve",
            "nimi",
            "henkilotunnus",
            "karttaosoite",
            "syntymavuosi",
            "h1_nimi",
            "h1_osoite",
            "h1_sahkoposti",
            "h1_puhelinnumero",
            "h2_nimi",
            "h2_osoite",
            "h2_sahkoposti",
            "h2_puhelinnumero",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
