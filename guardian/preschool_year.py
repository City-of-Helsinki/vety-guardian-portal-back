"""
The preschool (esiopetus) year that applications are currently made for.

`get_target_preschool_year()` is the ONLY place that decides it. For now the year is next calendar year
(an application made in 2026 is for the preschool year starting in autumn 2027), or ESIOPETUS_TARGET_YEAR
when that setting is set. When the preschool years are stored in a database (cf. the `Esiopetusvuosi` model in
vety-data-export-web), change only this function to read from there - callers stay as they are.
"""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

# A child starts preschool in the autumn of the year they turn six, i.e. preschool year = birth year + 6.
# Same rule as ESIOPETUS_IKA in vety-data-export-web (core/services/esiopetus/tulokkaat.py).
PRESCHOOL_AGE = 6

HELSINKI_TZ = ZoneInfo("Europe/Helsinki")


def get_target_preschool_year(today: date | None = None) -> int:
    """The preschool year applications are made for now."""
    if settings.ESIOPETUS_TARGET_YEAR:
        return int(settings.ESIOPETUS_TARGET_YEAR)
    if today is None:
        today = timezone.now().astimezone(HELSINKI_TZ).date()
    return today.year + 1


def target_birth_year(preschool_year: int) -> int:
    """The birth year of children who start preschool in `preschool_year`."""
    return preschool_year - PRESCHOOL_AGE
