from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from guardian.models.application import ApplicationStatus, PreschoolApplication
from guardian.vety import VetyConfigurationError, VetyError, send_application


class Command(BaseCommand):
    help = "Send the submitted applications that haven't been sent yet to hki-vety. Run periodically."

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("--limit", type=int, default=None, help="Send at most this many applications")

    def handle(self, *args: Any, **options: Any):
        unsent = PreschoolApplication.objects.filter(status=ApplicationStatus.SUBMITTED, vety_sent_at__isnull=True).order_by("submitted_at")
        if options["limit"] is not None:
            unsent = unsent[: options["limit"]]

        sent = 0
        failed: list[str] = []
        for application in unsent.iterator():
            try:
                send_application(application)
            except VetyConfigurationError as exc:
                raise CommandError(f"{exc}. Sent {sent} applications before stopping.") from exc
            except VetyError as exc:
                self.stderr.write(f"Application {application.pk}: {exc}")
                failed.append(str(application.pk))
                continue
            # update() instead of save(): don't touch updated_at or race with other fields.
            PreschoolApplication.objects.filter(pk=application.pk).update(vety_sent_at=timezone.now())
            sent += 1

        self.stdout.write(f"Sent {sent} applications to hki-vety.")
        if failed:
            raise CommandError(f"{len(failed)} applications could not be sent: {', '.join(failed)}")
