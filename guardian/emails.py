from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from .models.application import PreschoolApplication

logger = logging.getLogger(__name__)

SUBJECT = "Ilmoittautuminen esiopetukseen vastaanotettu / Anmälan till förskoleundervisning mottagen / Preschool enrolment received"


def confirmation_recipients(application: PreschoolApplication) -> list[str]:
    recipients: list[str] = []
    for email in (application.h1_sahkoposti, application.h2_sahkoposti):
        email = email.strip()
        if email and email.lower() not in (r.lower() for r in recipients):
            recipients.append(email)
    return recipients


def send_submission_confirmation(application: PreschoolApplication) -> int:
    body = render_to_string("guardian/email/submission_confirmation.txt")
    sent = 0
    for recipient in confirmation_recipients(application):
        message = EmailMessage(subject=SUBJECT, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient])
        try:
            sent += message.send()
        except Exception:
            logger.exception(f"Confirmation email for application {application.pk} could not be sent")
    return sent
