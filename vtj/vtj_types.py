"""
Typed representations of the VTJ response shapes used throughout this package,
so the rest of the code works with `Henkilo`/`Huollettava`/ `Huoltaja`/`Lahiosoite`
objects instead of parsing raw response dicts.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

logger = logging.getLogger("vety-guardian-portal-back")


def parse_vtj_date(value: str | None) -> datetime.date | None:
    """
    Parses a VTJ "Paivamaara" value (format YYYYMMDD, e.g. "20150710")
    into a `date`. Returns None (and logs a warning) instead of raising,
    since a malformed/missing date shouldn't block using the rest of an
    otherwise-valid record

     - VERIFY this format against your own first real response before relying on it.
    """
    if not value:
        return None
    try:
        return date.strptime(str(value), "%Y%m%d")
    except ValueError:
        logger.warning("Could not parse VTJ date value %r (expected YYYYMMDD)", value)
        return None


def ensure_list(value: Any) -> list[dict]:
    """Normalizes single-row dicts to a list (XSD maxOccurs=unbounded can still come back as one object in JSON)."""
    if not value:
        return []
    if isinstance(value, dict):
        return [value]
    return list(value)


def has_address_protection(henkilo: dict) -> bool:
    """
    Returns True if a Henkilo record has an active address-protection flag ("Turvakielto").
    Check this before displaying or storing address or contact information.
    """
    protection = (henkilo or {}).get("Turvakielto") or {}
    value = protection.get("TurvakieltoTieto")
    return str(value) not in {"0", "", "None", "none", "False", "false"}


@dataclass(frozen=True)
class Lahiosoite:
    """The VakinainenKotimainenLahiosoite (permanent domestic address) group of a Henkilo."""

    street_address: str
    postal_code: str
    postal_district: str

    @classmethod
    def from_henkilo(cls, henkilo: dict) -> Lahiosoite | None:
        """`henkilo` is a Henkilo dict. Returns None if the group is absent."""
        address = (henkilo or {}).get("VakinainenKotimainenLahiosoite")
        if not address:
            return None
        return cls(
            street_address=address.get("LahiosoiteS", "") or "",
            postal_code=address.get("Postinumero", "") or "",
            postal_district=address.get("PostitoimipaikkaS", "") or "",
        )


@dataclass(frozen=True)
class Huollettava:
    """One row from a Henkilo.Huollettava list - i.e. one of the queried person's dependants (wards)."""

    ssn: str
    last_name: str
    first_names: str
    date_of_birth: datetime.date | None

    @classmethod
    def from_row(cls, row: dict) -> Huollettava:
        return cls(
            ssn=row.get("Henkilotunnus", "") or "",
            last_name=(row.get("NykyinenSukunimi") or {}).get("Sukunimi", "") or "",
            first_names=(row.get("NykyisetEtunimet") or {}).get("Etunimet", "") or "",
            date_of_birth=parse_vtj_date(row.get("Syntymaaika")),
        )


@dataclass(frozen=True)
class Huoltaja:
    """One row from a Henkilo.Huoltaja list - i.e. one of the queried person's guardians."""

    ssn: str
    last_name: str
    first_names: str
    date_of_birth: datetime.date | None

    @classmethod
    def from_row(cls, row: dict) -> Huoltaja:
        return cls(
            ssn=row.get("Henkilotunnus", "") or "",
            last_name=(row.get("NykyinenSukunimi") or {}).get("Sukunimi", "") or "",
            first_names=(row.get("NykyisetEtunimet") or {}).get("Etunimet", "") or "",
            date_of_birth=parse_vtj_date(row.get("Syntymaaika")),
        )


@dataclass(frozen=True)
class Henkilo:
    """
    The Henkilo record of whoever was queried DIRECTLY.
    No `date_of_birth` field on purpose - it never
    appears here, only on nested Huollettava/Huoltaja rows.
    """

    ssn: str
    last_name: str
    first_names: str
    address_protected: bool
    address: Lahiosoite | None

    @classmethod
    def from_response(cls, ssn: str, henkilo: dict) -> Henkilo:
        henkilo = henkilo or {}
        return cls(
            ssn=ssn,
            last_name=(henkilo.get("NykyinenSukunimi") or {}).get("Sukunimi", "") or "",
            first_names=(henkilo.get("NykyisetEtunimet") or {}).get("Etunimet", "") or "",
            address_protected=has_address_protection(henkilo),
            address=Lahiosoite.from_henkilo(henkilo),
        )
