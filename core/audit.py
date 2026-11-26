"""
Audit log entries (kept 5 years in Platta's audit Elastic), written through django-resilient-logger.

Every entry goes through audit(), so the document shape is the same everywhere. The "resilient" handler of the
"audit" logger (settings.LOGGING) stores the entry in the database; Platta's CronJobs send it to Elastic. See
RESILIENT_LOGGER in settings.py.

Entry document (`audit_event` in Elastic):
- operation: CREATE / READ / UPDATE / DELETE
- actor: {"role", "uuid", "ip_address"}. SYSTEM entries have no uuid; entries without a request have no ip_address.
- target: {"object_ids": [...], "path"}. Entries without a request have no path.
- extra: {"status", "target_type", "helsinki_profile_id"} + the given extra; request_id is added from
  django-logger-extra's context, source_pk by resilient-logger.

No personal data beyond the actor's uuid, IP address and Helsinki-profiili id: never henkilötunnus, names,
addresses, emails or phone numbers. Targets are record ids and the message is a Message member (a fixed text).

Fail closed: errors are not caught. Call audit() inside the same transaction as the change, and before returning
data for reads, so that a failed write fails the request.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from enum import StrEnum
from uuid import UUID

from django.http import HttpRequest
from rest_framework.request import Request

from authentication.models import CustomUser

logger = logging.getLogger("audit")


class Operation(StrEnum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class Role(StrEnum):
    """Who acts, following the Helsinki-profiili roles."""

    # The guardian uses their own data: identity binding, their own application.
    OWNER = "OWNER"
    # The guardian reads another person's data: their dependants, a dependant's guardians.
    USER = "USER"
    # No person acts: the disclosure to vety-data-export-web, the GDPR API.
    SYSTEM = "SYSTEM"


class Message(StrEnum):
    """The entry's message: a fixed English text per event, never personal data. Add new events here."""

    # authentication
    IDENTITY_VERIFIED = "Identity verified"
    IDENTITY_UPDATED = "Identity updated"
    # vtj
    DEPENDANTS_LISTED = "Dependants listed"
    GUARDIANS_SAVED_FROM_VTJ = "Guardians saved from VTJ"
    DEPENDANTS_SAVED_FROM_VTJ = "Dependants saved from VTJ"
    # guardian (applications)
    APPLICATION_CREATED = "Application created"
    APPLICATION_OPENED = "Application opened"
    APPLICATION_SAVED = "Application saved"
    APPLICATION_SUBMITTED = "Application submitted"
    APPLICATION_PDF_DOWNLOADED = "Application PDF downloaded"
    # system
    APPLICATION_SENT = "Application sent to vety-data-export-web"
    GDPR_DATA_EXPORTED = "GDPR data exported"
    GDPR_DATA_DELETED = "GDPR data deleted"


class TargetType(StrEnum):
    APPLICATION = "application"
    GUARDIAN = "guardian"
    DEPENDANT = "dependant"
    USER = "user"


def client_ip(request: HttpRequest | Request) -> str | None:
    """The client's address. Behind Platta's router REMOTE_ADDR is the router, so the first X-Forwarded-For entry wins."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def audit(
    request: HttpRequest | Request | None,
    operation: Operation,
    message: Message,
    *,
    role: Role,
    target_type: TargetType,
    target_ids: Iterable[UUID | str],
    extra: dict[str, str] | None = None,
) -> None:
    """
    Writes one audit entry.

    :param request: the request, or None where the code doesn't get one (management commands, the GDPR functions).
        Required for OWNER and USER entries, whose actor is request.user (a logged-in CustomUser).
    :param message: the event, e.g. Message.APPLICATION_SUBMITTED.
    :param target_ids: ids of the records the operation concerns.
    :param extra: additional fixed values (strings), e.g. {"recipient": "vety-data-export-web"}.
    """
    actor: dict[str, str] = {"role": role}
    target: dict[str, str | list[str]] = {"object_ids": [str(target_id) for target_id in target_ids]}
    entry_extra: dict[str, str] = {**(extra or {}), "status": "SUCCESS", "target_type": target_type}

    if role != Role.SYSTEM:
        if request is None:
            raise ValueError(f"{role} audit entries need the request (the actor is request.user)")
        user = request.user
        # Also narrows the type for pyright: request.user is typed as AbstractBaseUser | AnonymousUser.
        if not isinstance(user, CustomUser):
            raise ValueError(f"{role} audit entries need a logged-in user, got {type(user).__name__}")
        actor["uuid"] = str(user.uuid)
        if user.helsinki_profile_id:
            entry_extra["helsinki_profile_id"] = str(user.helsinki_profile_id)

    if request is not None:
        ip_address = client_ip(request)
        if ip_address:
            actor["ip_address"] = ip_address
        target["path"] = request.path

    logger.info(message, extra={**entry_extra, "actor": actor, "operation": operation, "target": target})
