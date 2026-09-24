"""
Persists VTJ family data into the Guardian/Dependant models

`end_user` is required throughout because `client` itself
requires it (Loppukayttaja is mandatory on the underlying VTJ call, for
the Gateway's own traceability) - it is not stored anywhere by this module.
"""

from __future__ import annotations

import logging

from django.db import transaction

from . import client
from .exceptions import VTJError
from .models import Dependant, Guardian
from .vtj_types import Henkilo, Huoltaja

logger = logging.getLogger("vety-guardian-portal-back")


def _fetch_basic_info_safe(ssn: str, end_user: str) -> Henkilo:
    """
    Fetches `ssn`'s own `Henkilo` record via client.

    FAILS SAFE: if the call itself fails (network error, VTJ error), this
    returns a `Henkilo` with `address_protected=True` and `address=None` -
    i.e. treats the person as protected and address-less - rather than
    silently assuming they're unprotected.
    """
    try:
        return client.get_basic_info(ssn, end_user)
    except VTJError:
        # logger.warning("Could not fetch basic info for %s - treating as protected (fail-safe)", ssn, exc_info=True)
        logger.warning("Could not fetch address (get_basic_info failed)", exc_info=True)
        return Henkilo(ssn=ssn, last_name="", first_names="", address_protected=True, address=None)


def sync_family(guardian_ssn: str, end_user: str) -> bool:
    """
    Fetches and persists `guardian_ssn`'s whole family, then returns
    whether ANY family member has an active Turvakielto (address-
    protection) flag.


    :returns: True if any family member has an active Turvakielto flag.
    """
    guardian_self, dependants = client.get_dependants(guardian_ssn, end_user)
    dependant_ssns = [dependant.ssn for dependant in dependants if dependant.ssn]

    # Every dependant's own guardians.
    guardian_rows_by_dependant: dict[str, list[Huoltaja]] = {}
    henkilo_by_ssn: dict[str, Henkilo] = {guardian_ssn: guardian_self}
    for dependant_ssn in dependant_ssns:
        dependant_self, guardian_rows = client.get_guardians(dependant_ssn, end_user)
        guardian_rows_by_dependant[dependant_ssn] = guardian_rows
        henkilo_by_ssn[dependant_ssn] = dependant_self

    # Every guardian identity seen across all of those dependants.
    guardian_identity_by_ssn: dict[str, Huoltaja] = {}
    for rows in guardian_rows_by_dependant.values():
        for row in rows:
            if row.ssn:
                guardian_identity_by_ssn.setdefault(row.ssn, row)

    # Co-guardians are the only family members not already covered above.
    co_guardian_ssns = set(guardian_identity_by_ssn) - {guardian_ssn}
    for co_guardian_ssn in co_guardian_ssns:
        henkilo_by_ssn[co_guardian_ssn] = _fetch_basic_info_safe(co_guardian_ssn, end_user)

    is_protected_family = any(henkilo.address_protected for henkilo in henkilo_by_ssn.values())

    with transaction.atomic():
        guardians_by_ssn = {ssn: Guardian.update_or_create_from_identity(ssn, identity) for ssn, identity in guardian_identity_by_ssn.items()}

        # The queried guardian is persisted even without dependants (no Huoltaja rows mention them then).
        queried_guardian = guardians_by_ssn.get(guardian_ssn) or Guardian.update_or_create_from_identity(guardian_ssn)
        if guardian_ssn not in guardian_identity_by_ssn:
            queried_guardian.last_name = guardian_self.last_name
            queried_guardian.first_names = guardian_self.first_names
        guardians_by_ssn[guardian_ssn] = queried_guardian

        dependants_by_ssn = {dependant.ssn: Dependant.update_or_create_from_identity(dependant.ssn, dependant) for dependant in dependants if dependant.ssn}

        # Link dependant's own guardians for each dependant
        for dependant_ssn, guardian_rows in guardian_rows_by_dependant.items():
            dependant = dependants_by_ssn[dependant_ssn]
            for guardian in guardian_rows:
                guardian = guardians_by_ssn.get(guardian.ssn)
                if guardian is not None:
                    dependant.guardians.add(guardian)

        for ssn, henkilo in henkilo_by_ssn.items():
            person = guardians_by_ssn.get(ssn) or dependants_by_ssn.get(ssn)
            if person is None:
                continue
            person.update_address(henkilo.address, address_protected=henkilo.address_protected, withhold=is_protected_family)
            person.save()

    return is_protected_family
