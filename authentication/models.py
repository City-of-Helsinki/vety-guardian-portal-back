from typing import Any

from django.db import models
from helsinki_gdpr.models import SerializableMixin
from helusers.models import AbstractUser


class CustomUser(AbstractUser, SerializableMixin):
    """
    Internal user account.
    Created by helusers from the Helsinki-profiili (Tunnistus) API token: `uuid` is the token's `sub`.
    Also the GDPR API model (GDPR_API_MODEL, see authentication/gdpr.py).
    """

    # Fields returned by the GDPR API query.
    serialize_fields = (
        {"name": "uuid"},
        {"name": "username"},
        {"name": "first_name"},
        {"name": "last_name"},
        {"name": "email"},
        {"name": "national_identification_number"},
        {"name": "helsinki_profile_id"},
        {"name": "date_joined"},
        {"name": "last_login"},
    )

    # Filled from Helsinki-profiili's verifiedPersonalInformation (see authentication/views.py).
    # Empty until the user has verified their identity (Suomi.fi) in this app.
    national_identification_number = models.CharField("henkilötunnus", max_length=11, blank=True)
    # Helsinki-profiili profile id (not the Tunnistus `sub` in `uuid`), stored with the henkilötunnus.
    # Sent to VTJ as Loppukayttaja (see vtj/views.py).
    helsinki_profile_id = models.UUIDField("Helsinki-profiili id", null=True, blank=True)

    def __str__(self):
        return self.username

    def serialize(self) -> dict[str, Any]:
        from .gdpr import serialize_related_data

        data = super().serialize()
        data["children"].extend(serialize_related_data(self))
        return data
