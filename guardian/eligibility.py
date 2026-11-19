"""
Who a preschool (esiopetus) application can be made for.

A child is eligible when
1. they are of preschool age: birth year + PRESCHOOL_AGE == the target preschool year (guardian/preschool_year.py), and
2. their home municipality is Helsinki (`is_allowed_municipality`).

The rules are enforced by the backend in two places - when a draft is created
(PreschoolApplicationForDependantView) and when an application is submitted
(PreschoolApplicationSerializer) - and exposed to the frontend on the dependant list, so it can show why a
child can't apply. The frontend never re-implements the rules.

HOME MUNICIPALITY: NAME VS. CODE
--------------------------------
Two settings, exactly one of which is used:

- ESIOPETUS_MUNICIPALITY_NAME (e.g. "Helsinki"): always used when set. Compared, ignoring case and surrounding
  whitespace, to the child's postal district (VTJ VakinainenKotimainenLahiosoite/PostitoimipaikkaS, stored as
  `postal_district`).
- ESIOPETUS_MUNICIPALITY_CODE (e.g. "091"): used only when the name is not set. Compared to the child's VTJ
  Kotikunta/Kuntanumero (stored as `home_municipality_code`).

Why the code would be better: a postal district is a postal delivery area, not a municipality - near municipal
borders the two can differ, and its spelling varies (the VTJ mock alone has both "Helsinki" and "HELSINKI").
Kotikunta/Kuntanumero is the official home municipality in the Population Information System, which is what the
right to preschool in Helsinki is actually based on, and the municipality number is a stable, language-independent
identifier (no "Helsinki" vs. "Helsingfors").

Where "091" comes from: Statistics Finland's municipality classification (Tilastokeskuksen kuntaluokitus), where
Helsinki is 091. We ASSUME VTJ's KuntanumeroTyyppi uses the same 3-character, zero-padded format (the example
response in vtj/schemas/peruslt1esimerkkivastaus.xml has Varkaus as "915"), but this has NOT been verified
against a real VTJ response in this project.

How to verify that the code works with the VTJ interface before switching to it:
1. Check the definition of KuntanumeroTyyppi in DVV's VTJ interface description (string? length 3? leading zeros?).
2. Query the VTJ test environment (HenkilonTunnuskysely) for a test person living in Helsinki and inspect the raw
   <Kotikunta><Kuntanumero> value, e.g. in `manage.py shell` with `vtj.client.get_basic_info(ssn, end_user)` and
   its `home_municipality_code`.
3. After a guardian's family has been synced, check that the dependants' stored `home_municipality_code` is "091".
4. Then switch: set ESIOPETUS_MUNICIPALITY_NAME to an empty value and ESIOPETUS_MUNICIPALITY_CODE=091.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .preschool_year import PRESCHOOL_AGE, get_target_preschool_year

if TYPE_CHECKING:
    from vtj.models import Dependant

# Reason codes. Stable: the frontend translates them (Locize keys errors.<code>, and eligibility.notResidentHelsinki
# for the dependant list notice).
NOT_PRESCHOOL_AGE = "not_preschool_age"
NOT_RESIDENT_HELSINKI = "not_resident_helsinki"


def _normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


def is_allowed_municipality(home_municipality_code: str | None, postal_district: str | None) -> bool:
    """
    Whether the child's home municipality is the allowed one. Missing data is never allowed.
    See the module docstring for why there are two settings and which one wins.
    """
    name = _normalize(settings.ESIOPETUS_MUNICIPALITY_NAME)
    if name:
        return _normalize(postal_district) == name
    code = (settings.ESIOPETUS_MUNICIPALITY_CODE or "").strip()
    if code:
        return (home_municipality_code or "").strip() == code
    raise ImproperlyConfigured("Set ESIOPETUS_MUNICIPALITY_NAME or ESIOPETUS_MUNICIPALITY_CODE.")


def check_eligibility(dependant: Dependant, target_year: int | None = None) -> list[str]:
    """
    Returns the reasons an application can't be made for `dependant`; an empty list means it can.

    Age is checked first and, when it fails, returned alone: the frontend shows no explanation for a child of the
    wrong age, and the home municipality message only for a child of the right age.
    """
    if target_year is None:
        target_year = get_target_preschool_year()

    if dependant.date_of_birth is None or dependant.date_of_birth.year + PRESCHOOL_AGE != target_year:
        return [NOT_PRESCHOOL_AGE]
    if not is_allowed_municipality(dependant.home_municipality_code, dependant.postal_district):
        return [NOT_RESIDENT_HELSINKI]
    return []
