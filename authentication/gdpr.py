"""
https://github.com/City-of-Helsinki/helsinki-profile-gdpr-api
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models
from django.db.models import Q

from guardian.models.application import PreschoolApplication
from vtj.models import Guardian

if TYPE_CHECKING:
    from .models import CustomUser


def _serialize_instance(instance: models.Model) -> dict[str, Any]:
    return {
        "key": instance._meta.model_name.upper(),  # pyright: ignore[reportOptionalMemberAccess]
        "children": [{"key": field.name.upper(), "value": field.value_from_object(instance)} for field in instance._meta.concrete_fields],
    }


def serialize_related_data(user: CustomUser) -> list[dict[str, Any]]:
    """
    All data related to the user outside CustomUser (applications, VTJ-records)
    """
    hetu = user.national_identification_number
    if not hetu:
        return []

    applications = PreschoolApplication.objects.filter(Q(h1_henkilotunnus=hetu) | Q(h2_henkilotunnus=hetu)).order_by("created_at")
    guardians = Guardian.objects.filter(ssn=hetu)
    return [
        {"key": "PRESCHOOLAPPLICATIONS", "children": [_serialize_instance(application) for application in applications]},
        {"key": "GUARDIANS", "children": [_serialize_instance(guardian) for guardian in guardians]},
    ]


def get_user(user: CustomUser) -> CustomUser:
    """
    GDPR_API_USER_PROVIDER
    """
    return user


def delete_gdpr_data(user: CustomUser, dry_run: bool) -> None:
    """
    GDPR_API_DELETER
    """
    user.delete()
