from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


# test_command.py
class Command(BaseCommand):
    help = "Test command"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("name", type=str, help="Your name")
        parser.add_argument("--times", type=int, default=1, help="Number of greetings")

    def handle(self, *args: Any, **options: Any):
        if not settings.DEBUG:
            raise CommandError("This command can only be run when DEBUG=True.")

        self.stdout.write(f"args: {args!s}")
        self.stdout.write(f"options: {options!s}")

        name = options["name"]
        times = options["times"]

        for i in range(times):
            self.stdout.write(f"Hello, {name}! ({i + 1})")

        self.stdout.write(self.style.SUCCESS("Test command was successfully."))
