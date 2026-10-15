from django.db import models
from helusers.models import AbstractUser


class CustomUser(AbstractUser):
    """
    Internal user account.
    Created by helusers from the Helsinki-profiili (Tunnistus) API token: `uuid` is the token's `sub`.
    """

    # Filled from Helsinki-profiili's verifiedPersonalInformation (see authentication/views.py).
    # Empty until the user has verified their identity (Suomi.fi) in this app.
    national_identification_number = models.CharField("henkilötunnus", max_length=11, blank=True)
    # Helsinki-profiili profile id (not the Tunnistus `sub` in `uuid`), stored with the henkilötunnus.
    # Sent to VTJ as Loppukayttaja (see vtj/views.py).
    helsinki_profile_id = models.UUIDField("Helsinki-profiili id", null=True, blank=True)

    def __str__(self):
        return self.username
