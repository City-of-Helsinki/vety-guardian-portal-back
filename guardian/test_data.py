"""
Deletes test data so e2e tests can start from a clean state.
Used by the db_delete_* commands and the test-data API (guardian/testing/).
"""

from django.db import transaction
from django.db.models import Q

from vtj.models import Dependant, Guardian

from .models.application import PreschoolApplication


@transaction.atomic
def delete_data_for_hetu(hetu: str) -> dict[str, int]:
    """
    Deletes the applications and VTJ person records linked to `hetu`, which may be a child's or a guardian's.
    With a guardian's hetu, all of the guardian's dependants and their applications are deleted too.
    The VTJ records are recreated by the next VTJ sync.
    """
    hetu = hetu.strip()
    if not hetu:
        # An empty hetu would match every application with a blank henkilotunnus.
        raise ValueError("hetu must not be empty")

    dependant_ids = list(Dependant.objects.filter(Q(ssn=hetu) | Q(guardians__ssn=hetu)).values_list("id", flat=True).distinct())
    # Applications first: PreschoolApplication.dependant is on_delete=PROTECT.
    _, applications = PreschoolApplication.objects.filter(Q(henkilotunnus=hetu) | Q(dependant_id__in=dependant_ids)).delete()
    _, dependants = Dependant.objects.filter(id__in=dependant_ids).delete()
    _, guardians = Guardian.objects.filter(ssn=hetu).delete()

    return {
        "applications": applications.get(PreschoolApplication._meta.label, 0),
        "dependants": dependants.get(Dependant._meta.label, 0),
        "guardians": guardians.get(Guardian._meta.label, 0),
    }


def delete_all_applications() -> dict[str, int]:
    """Deletes all rows from the PreschoolApplication table."""
    _, applications = PreschoolApplication.objects.all().delete()
    return {"applications": applications.get(PreschoolApplication._meta.label, 0)}
