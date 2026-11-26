from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from guardian.eligibility import NOT_PRESCHOOL_AGE, NOT_RESIDENT_HELSINKI, check_eligibility
from guardian.preschool_year import get_target_preschool_year

from .models import Dependant

# Person fields exposed by DependantSerializer
PERSON_FIELDS = [
    "id",
    "ssn",
    "first_names",
    "last_name",
    "date_of_birth",
    "street_address",
    "postal_code",
    "postal_district",
    "address_protected",
]


class EligibilitySerializer(serializers.Serializer):
    """Schema-only: whether a preschool application can be made for the dependant (guardian/eligibility.py)."""

    can_apply = serializers.BooleanField()
    # Why not, when can_apply is false. "not_preschool_age" is always alone (checked first).
    reasons = serializers.ListField(child=serializers.ChoiceField(choices=[NOT_PRESCHOOL_AGE, NOT_RESIDENT_HELSINKI]))
    # The preschool year applications are made for now, e.g. 2027.
    target_preschool_year = serializers.IntegerField()


class DependantSerializer(serializers.ModelSerializer):
    eligibility = serializers.SerializerMethodField()

    class Meta:
        model = Dependant
        fields = [*PERSON_FIELDS, "eligibility"]
        read_only_fields = fields

    @extend_schema_field(EligibilitySerializer)
    def get_eligibility(self, instance: Dependant) -> dict:
        target_year = get_target_preschool_year()
        reasons = check_eligibility(instance, target_year)
        return {"can_apply": not reasons, "reasons": reasons, "target_preschool_year": target_year}


class DependantsResponseSerializer(serializers.Serializer):
    """Schema-only: the `GET /dependants/` response envelope."""

    dependants = DependantSerializer(many=True)


class IsProtectedFamilyResponseSerializer(serializers.Serializer):
    """Schema-only: the `GET /is_protected_family/` response envelope."""

    is_protected_family = serializers.BooleanField()


class ErrorResponseSerializer(serializers.Serializer):
    """Schema-only: the `{"error": "...", "code": "..."}` body every error response uses."""

    error = serializers.CharField()
    # Stable machine-readable code the frontend translates (e.g. "vtj_person_not_found"); `error` is for logs/devs.
    code = serializers.CharField(required=False)
