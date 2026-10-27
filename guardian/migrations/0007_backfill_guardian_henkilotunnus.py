# Applications created before 0006 have no guardian henkilötunnus -> current_guardian is null for them.
# Backfills it by matching h1_nimi / h2_nimi against the dependant's guardians.

from django.db import migrations


def full_name(person) -> str:
    return " ".join(part for part in (person.first_names, person.last_name) if part)


def backfill(apps, schema_editor):
    PreschoolApplication = apps.get_model("guardian", "PreschoolApplication")
    applications = PreschoolApplication.objects.filter(dependant__isnull=False).prefetch_related("dependant__guardians")
    for application in applications:
        ssn_by_name = {full_name(g): g.ssn for g in application.dependant.guardians.all()}
        changed = False
        for slot in ("h1", "h2"):
            name = getattr(application, f"{slot}_nimi")
            if not getattr(application, f"{slot}_henkilotunnus") and name in ssn_by_name:
                setattr(application, f"{slot}_henkilotunnus", ssn_by_name[name])
                changed = True
        if changed:
            application.save(update_fields=["h1_henkilotunnus", "h2_henkilotunnus"])


class Migration(migrations.Migration):
    dependencies = [
        ("guardian", "0006_guardian_henkilotunnus"),
        ("vtj", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
