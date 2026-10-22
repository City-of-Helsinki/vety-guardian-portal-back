from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from guardian.test_data import delete_data_for_hetu


# db_delete_by_hetu.py
class Command(BaseCommand):
    help = "Removes the applications and VTJ person records linked to a child's or guardian's henkilötunnus"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("hetu", type=str, help="Child's or guardian's henkilötunnus whose data is deleted")
        parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")

    def handle(self, *args: Any, **options: Any):
        if not settings.DEBUG:
            raise CommandError("This command can only be run when DEBUG=True.")

        hetu: str = options["hetu"].strip()
        if not hetu:
            raise CommandError("hetu must not be empty.")

        self.stdout.write(self.style.WARNING(f"Data linked to henkilötunnus {hetu} will be deleted!"))
        if not options["yes"]:
            confirm = input("Do you want to continue? Type 'Yes' to proceed: ")
            if confirm != "Yes":
                self.stdout.write(self.style.NOTICE("Operation cancelled."))
                return

        counts = delete_data_for_hetu(hetu)
        self.stdout.write(self.style.SUCCESS(f"Delete command completed: {counts}"))
