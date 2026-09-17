from __future__ import annotations

from rest_framework import serializers

from .models import Dependant, Guardian

# Shared between both serializers below so Guardian/Dependant stay exposed identically
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


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = PERSON_FIELDS
        read_only_fields = PERSON_FIELDS  # these views are read-only - see views.py


class DependantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dependant
        fields = PERSON_FIELDS
        read_only_fields = PERSON_FIELDS


class DependantsResponseSerializer(serializers.Serializer):
    """Schema-only: the `GET /dependants/` response envelope."""

    dependants = DependantSerializer(many=True)


class GuardiansResponseSerializer(serializers.Serializer):
    """Schema-only: the `GET /guardians/<dependant_id>/` response envelope."""

    dependant = DependantSerializer()
    guardians = GuardianSerializer(many=True)


class IsProtectedFamilyResponseSerializer(serializers.Serializer):
    """Schema-only: the `GET /is_protected_family/` response envelope."""

    is_protected_family = serializers.BooleanField()


class ErrorResponseSerializer(serializers.Serializer):
    """Schema-only: the `{"error": "..."}` body every error response uses."""

    error = serializers.CharField()
