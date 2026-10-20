import uuid

from django.db import migrations, models


def set_uuids(apps, schema_editor):
    CustomUser = apps.get_model("authentication", "CustomUser")
    for user in CustomUser.objects.filter(uuid__isnull=True):
        user.uuid = uuid.uuid1()
        user.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0001_initial"),
        ("helusers", "0002_add_oidcbackchannellogoutevent"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="customuser",
            options={"ordering": ("id",)},
        ),
        # helusers.models.AbstractUser fields. uuid is added nullable first so existing users get unique values.
        migrations.AddField(
            model_name="customuser",
            name="uuid",
            field=models.UUIDField(null=True),
        ),
        migrations.RunPython(set_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customuser",
            name="uuid",
            field=models.UUIDField(unique=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="department_name",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="ad_groups",
            field=models.ManyToManyField(blank=True, to="helusers.adgroup"),
        ),
        migrations.AddField(
            model_name="customuser",
            name="last_api_use",
            field=models.DateField(blank=True, null=True, verbose_name="Latest API token usage date"),
        ),
        migrations.AddField(
            model_name="customuser",
            name="national_identification_number",
            field=models.CharField(blank=True, max_length=11, verbose_name="henkilötunnus"),
        ),
    ]
