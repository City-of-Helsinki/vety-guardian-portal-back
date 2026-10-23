from typing import Any

from django.db import models
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models.application import ApplicationStatus, PreschoolApplication

REQUIRED_MESSAGE = "This field is required."

CURRENT_GUARDIAN_CHOICES = ["h1", "h2"]

# The contact details each guardian enters themselves.
GUARDIAN_CONTACT_FIELDS = {
    "h1": ["h1_sahkoposti", "h1_puhelinnumero"],
    "h2": ["h2_sahkoposti", "h2_puhelinnumero"],
}


class PreschoolApplicationSerializer(serializers.ModelSerializer):
    """
    Serializer for PreschoolApplication.

    Drafts accept any subset of fields, and null / empty values.
    Full validation is run only when the status is changed to "submitted".
    Submitted applications cannot be modified.
    """

    current_guardian = serializers.SerializerMethodField()

    class Meta:
        model = PreschoolApplication
        fields = [
            "id",
            "created_at",
            "updated_at",
            "status",
            "submitted_at",
            "hakenut_ensisijaisesti_yksityiseen",
            "kieli",
            "taydentava_varhaiskasvatus",
            "taydentava_varhaiskasvatus_aloitus",
            "hoidon_tarve",
            "palvelun_tarve",
            "arkipoissaolot_lkm",
            "erityisen_tuen_tarve",
            "laakehoidon_tarve",
            "dependant",
            "nimi",
            "henkilotunnus",
            "karttaosoite",
            "syntymavuosi",
            "h1_nimi",
            "h1_osoite",
            "h1_henkilotunnus",
            "h1_sahkoposti",
            "h1_puhelinnumero",
            "h2_nimi",
            "h2_osoite",
            "h2_henkilotunnus",
            "h2_sahkoposti",
            "h2_puhelinnumero",
            "current_guardian",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "submitted_at",
            # Set from VTJ by PreschoolApplicationForDependantView only.
            "dependant",
            "nimi",
            "henkilotunnus",
            "karttaosoite",
            "syntymavuosi",
            "h1_nimi",
            "h1_osoite",
            "h1_henkilotunnus",
            "h2_nimi",
            "h2_osoite",
            "h2_henkilotunnus",
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # In the draft, all fields are optional and can be null.
        for name, field in self.fields.items():
            if field.read_only or name == "status":
                continue
            field.required = False
            field.allow_null = True
            if isinstance(field, serializers.ChoiceField):
                field.allow_blank = True

    @extend_schema_field(serializers.ChoiceField(choices=CURRENT_GUARDIAN_CHOICES, allow_null=True, read_only=True))
    def get_current_guardian(self, instance: PreschoolApplication) -> str | None:
        """Which guardian slot (h1 / h2) the logged-in user is in."""
        request = self.context.get("request")
        ssn = getattr(getattr(request, "user", None), "national_identification_number", "")
        if not ssn:
            return None
        if ssn == instance.h1_henkilotunnus:
            return "h1"
        if ssn == instance.h2_henkilotunnus:
            return "h2"
        return None

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance: PreschoolApplication | None = self.instance

        # The text fields in the database are not nullable -> nulls are stored as empty strings.
        for name, value in attrs.items():
            if value is None and isinstance(PreschoolApplication._meta.get_field(name), models.CharField):
                attrs[name] = ""

        if instance is not None and instance.status == ApplicationStatus.SUBMITTED:
            raise serializers.ValidationError({"status": "Submitted application cannot be edited."})

        # Guardians can only edit their own contact details -> the other guardian's are ignored.
        current_guardian = self.get_current_guardian(instance) if instance else None
        for guardian, fields in GUARDIAN_CONTACT_FIELDS.items():
            if guardian != current_guardian:
                for name in fields:
                    attrs.pop(name, None)

        status = attrs.get("status", ApplicationStatus.DRAFT)
        if instance is None and status != ApplicationStatus.DRAFT:
            raise serializers.ValidationError({"status": "New application is created as a draft."})

        if status == ApplicationStatus.SUBMITTED:
            data = {name: getattr(instance, name) for name in self.Meta.fields if name != "current_guardian"} if instance else {}
            data.update(attrs)
            self._validate_submission(data)

        return attrs

    def _validate_submission(self, data: dict[str, Any]) -> None:
        required = ["kieli", "hakenut_ensisijaisesti_yksityiseen", "taydentava_varhaiskasvatus", "h1_sahkoposti"]
        if data.get("taydentava_varhaiskasvatus"):
            required += ["taydentava_varhaiskasvatus_aloitus", "hoidon_tarve", "palvelun_tarve", "arkipoissaolot_lkm"]

        errors = {name: [REQUIRED_MESSAGE] for name in required if data.get(name) in (None, "")}
        if errors:
            raise serializers.ValidationError(errors)

    def update(self, instance: PreschoolApplication, validated_data: dict[str, Any]) -> PreschoolApplication:
        if validated_data.get("status") == ApplicationStatus.SUBMITTED:
            validated_data["submitted_at"] = timezone.now()
        return super().update(instance, validated_data)
