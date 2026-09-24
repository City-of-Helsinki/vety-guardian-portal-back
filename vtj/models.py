"""
Django models for persisting the "Huollettava" (dependant/ward) and
"Huoltaja" (guardian) data groups returned by the VTJ HenkilonTunnuskysely
interface.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Self

from django.core.validators import RegexValidator
from django.db import models

from guardian.models.base import BaseModel

from .vtj_types import Huollettava, Huoltaja, Lahiosoite

if TYPE_CHECKING:
    from django.db.models.manager import BaseManager

    from guardian.models.application import PreschoolApplication

logger = logging.getLogger("vety-guardian-portal-back")

# Soft format check only - a Finnish "henkilotunnus" is DDMMYY + century
# sign + 3-digit individual number + 1 check character. This does NOT
# validate the checksum or century sign correctness, only the shape - VTJ
# itself is the source of truth for whether an identity code is valid.
_SSN_VALIDATOR = RegexValidator(
    regex=r"^\d{6}[-+A]\d{3}[0-9A-Y]$",
    message="Not in the expected Finnish henkilotunnus format (e.g. 010101-1234).",
)


class PersonRecord(BaseModel):
    """
    Common fields for a Guardian or Dependant record - i.e. everything a
    Huoltaja/Huollettava row from VTJ actually contains, plus address.
    Abstract: it only exists to avoid repeating the same fields on both concrete
    models below.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ssn = models.CharField(
        "henkilötunnus",
        max_length=11,
        unique=True,
        validators=[_SSN_VALIDATOR],
        help_text="Finnish personal identity code (Henkilotunnus).",
    )
    last_name = models.CharField("sukunimi", max_length=100, blank=True)
    first_names = models.CharField("etunimet", max_length=100, blank=True)
    date_of_birth = models.DateField("syntymäaika", null=True, blank=True)

    # Populated by sync.py from a vtj_types.Henkilo record.
    # Left blank whenever address_protected is True.
    street_address = models.CharField("lähiosoite", max_length=200, blank=True)
    postal_code = models.CharField("postinumero", max_length=10, blank=True)
    postal_district = models.CharField("postitoimipaikka", max_length=100, blank=True)
    address_protected = models.BooleanField(
        "turvakielto",
        default=False,
        help_text="True if this person's VTJ record has an active address-protection flag (Turvakielto).",
    )

    class Meta(BaseModel.Meta):
        abstract = True
        ordering = ["last_name", "first_names"]

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_names, self.last_name) if part)

    def format_address(self) -> str:
        """
        Returns the address as "<street_address>, <postal_code> <postal_district>", skipping empty parts.
        Empty string when the address is withheld (Turvakielto) or missing.
        """
        postal = " ".join(part for part in (self.postal_code, self.postal_district) if part)
        return ", ".join(part for part in (self.street_address, postal) if part)

    def update_from_identity(self, identity: Huollettava | Huoltaja) -> None:
        """
        Updates this instance's fields in place (does not save()) from a `Huollettava`/`Huoltaja` row.
        """
        self.last_name = identity.last_name
        self.first_names = identity.first_names
        self.date_of_birth = identity.date_of_birth

    def update_address(self, address: Lahiosoite | None, *, address_protected: bool, withhold: bool) -> None:
        """
        Updates this instance's address fields in place (does not save()).
        `address_protected` is recorded as-is regardless of `withhold`.
        """
        self.address_protected = address_protected
        if withhold or address_protected or address is None:
            self.street_address = ""
            self.postal_code = ""
            self.postal_district = ""
        else:
            self.street_address = address.street_address
            self.postal_code = address.postal_code
            self.postal_district = address.postal_district

    @classmethod
    def update_or_create_from_identity(cls, ssn: str, identity: Huollettava | Huoltaja | None = None) -> Self:
        """
        Gets or creates a record by ssn and updates it with the fields
        from `identity` (a `Huollettava`/`Huoltaja` dataclass), if given.
        """
        instance, _created = cls.objects.get_or_create(ssn=ssn)
        if identity is not None:
            instance.update_from_identity(identity)
            instance.save()
        return instance


class Guardian(PersonRecord):
    """A person acting as a guardian (Huoltaja) of one or more dependants."""

    if TYPE_CHECKING:
        # annotate-only dynamically generated attributes
        dependants: BaseManager[Dependant]

    class Meta(PersonRecord.Meta):
        verbose_name = "guardian"
        verbose_name_plural = "guardians"


class Dependant(PersonRecord):
    """A person under guardianship (Huollettava) of one or more guardians."""

    if TYPE_CHECKING:
        # annotate-only dynamically generated attributes
        applications: BaseManager[PreschoolApplication]

    guardians = models.ManyToManyField(
        Guardian,
        related_name="dependants",
        blank=True,
    )

    class Meta(PersonRecord.Meta):
        verbose_name = "dependant"
        verbose_name_plural = "dependants"
