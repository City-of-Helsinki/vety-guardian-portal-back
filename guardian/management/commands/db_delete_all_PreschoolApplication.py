from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from guardian.test_data import delete_all_applications


# db_edlevo_delete.py.py
class Command(BaseCommand):
    help = "Removed all data from table 'PreschoolApplication'"

    def handle(self, *args: Any, **options: Any):
        if not settings.DEBUG:
            raise CommandError("This command can only be run when DEBUG=True.")

        self.stdout.write(self.style.WARNING("Data will be deleted!"))
        confirm = input("Do you want to continue? Type 'Yes' to proceed: ")

        if confirm != "Yes":
            self.stdout.write(self.style.NOTICE("Operation cancelled."))
            return

        self.delete_all_paikkatoive_esi()

    def delete_all_paikkatoive_esi(self) -> None:
        self.stdout.write("Delete all from table 'PreschoolApplication'")
        counts = delete_all_applications()
        self.stdout.write(self.style.SUCCESS(f"Delete command completed: {counts}"))
