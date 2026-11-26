import json
import logging
import uuid
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse
from resilient_logger.errors.missing_context_error import MissingContextError
from resilient_logger.models import ResilientLogEntry
from resilient_logger.sources.resilient_log_source_entry import ResilientLogSourceEntry
from resilient_logger.utils import get_resilient_logger_config
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import CustomUser
from core.audit import Message, Operation, Role, TargetType, audit
from vtj.models import Dependant, Guardian

GUARDIAN_SSN = "010170-999X"
CHILD_SSN = "010118-9998"
SIBLING_SSN = "020218-9998"

# Where the "resilient" handler writes; patched to simulate a failing database write.
CREATE_ENTRY = "resilient_logger.sources.ResilientLogSource.create"


def only_entry(test: TestCase) -> ResilientLogEntry:
    entries = list(ResilientLogEntry.objects.all())
    test.assertEqual(len(entries), 1)
    return entries[0]


class AuditTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(uuid=uuid.uuid4(), national_identification_number=GUARDIAN_SSN, helsinki_profile_id=uuid.uuid4())

    def request(self, **meta: str):
        request = RequestFactory().get("/vtj/dependants/", **meta)  # pyright: ignore[reportArgumentType]
        request.user = self.user
        return request

    def test_user_entry(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        audit(self.request(REMOTE_ADDR="10.0.0.1"), Operation.READ, Message.DEPENDANTS_LISTED, role=Role.USER, target_type=TargetType.DEPENDANT, target_ids=ids)

        entry = only_entry(self)
        self.assertEqual(entry.message, "Dependants listed")
        self.assertEqual(entry.level, logging.INFO)
        context = entry.context
        self.assertEqual(context["operation"], "READ")
        self.assertEqual(context["actor"], {"role": "USER", "uuid": str(self.user.uuid), "ip_address": "10.0.0.1"})
        self.assertEqual(context["target"], {"object_ids": [str(i) for i in ids], "path": "/vtj/dependants/"})
        self.assertEqual(context["status"], "SUCCESS")
        self.assertEqual(context["target_type"], "dependant")
        self.assertEqual(context["helsinki_profile_id"], str(self.user.helsinki_profile_id))

    def test_client_ip_from_first_forwarded_for_address(self):
        request = self.request(HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.2", REMOTE_ADDR="10.0.0.1")
        audit(request, Operation.READ, Message.APPLICATION_OPENED, role=Role.OWNER, target_type=TargetType.APPLICATION, target_ids=[uuid.uuid4()])

        self.assertEqual(only_entry(self).context["actor"]["ip_address"], "203.0.113.5")

    def test_system_entry_without_request(self):
        application_id = uuid.uuid4()
        audit(
            None,
            Operation.READ,
            Message.APPLICATION_OPENED,
            role=Role.SYSTEM,
            target_type=TargetType.APPLICATION,
            target_ids=[application_id],
            extra={"recipient": "vety-data-export-web"},
        )

        context = only_entry(self).context
        self.assertEqual(context["actor"], {"role": "SYSTEM"})
        self.assertEqual(context["target"], {"object_ids": [str(application_id)]})
        self.assertEqual(context["recipient"], "vety-data-export-web")
        self.assertNotIn("helsinki_profile_id", context)

    def test_system_entry_with_request_has_no_user(self):
        audit(
            self.request(REMOTE_ADDR="10.0.0.1"),
            Operation.DELETE,
            Message.IDENTITY_UPDATED,
            role=Role.SYSTEM,
            target_type=TargetType.USER,
            target_ids=[self.user.uuid],
        )

        context = only_entry(self).context
        self.assertEqual(context["actor"], {"role": "SYSTEM", "ip_address": "10.0.0.1"})
        self.assertNotIn("helsinki_profile_id", context)

    def test_user_entry_needs_request(self):
        with self.assertRaises(ValueError):
            audit(None, Operation.READ, Message.DEPENDANTS_LISTED, role=Role.USER, target_type=TargetType.DEPENDANT, target_ids=[])
        self.assertFalse(ResilientLogEntry.objects.exists())

    def test_user_entry_needs_logged_in_user(self):
        request = self.request()
        request.user = AnonymousUser()
        with self.assertRaises(ValueError):
            audit(request, Operation.READ, Message.DEPENDANTS_LISTED, role=Role.USER, target_type=TargetType.DEPENDANT, target_ids=[])
        self.assertFalse(ResilientLogEntry.objects.exists())

    def test_extra_does_not_override_standard_fields(self):
        audit(
            None,
            Operation.READ,
            Message.IDENTITY_VERIFIED,
            role=Role.SYSTEM,
            target_type=TargetType.USER,
            target_ids=[],
            extra={"status": "FORBIDDEN", "target_type": "other"},
        )

        context = only_entry(self).context
        self.assertEqual(context["status"], "SUCCESS")
        self.assertEqual(context["target_type"], "user")

    def test_failed_write_raises(self):
        with mock.patch(CREATE_ENTRY, side_effect=RuntimeError("database down")), self.assertRaises(RuntimeError):
            audit(None, Operation.READ, Message.IDENTITY_VERIFIED, role=Role.SYSTEM, target_type=TargetType.USER, target_ids=[])

    def test_audit_logger_requires_actor_operation_and_target(self):
        """settings.LOGGING: the "audit" logger writes through the "resilient" handler, with required_fields."""
        with self.assertRaises(MissingContextError):
            logging.getLogger("audit").info("x", extra={"actor": {"role": "SYSTEM"}, "operation": "READ"})
        self.assertFalse(ResilientLogEntry.objects.exists())

    def test_document_sent_to_elastic(self):
        get_resilient_logger_config.cache_clear()
        self.addCleanup(get_resilient_logger_config.cache_clear)
        ids = [uuid.uuid4()]
        audit(self.request(REMOTE_ADDR="10.0.0.1"), Operation.READ, Message.DEPENDANTS_LISTED, role=Role.USER, target_type=TargetType.DEPENDANT, target_ids=ids)

        entry = only_entry(self)
        document = ResilientLogSourceEntry(entry).get_document()
        event = document["audit_event"]
        self.assertIn("@timestamp", document)
        self.assertEqual(event["origin"], "vety-guardian-portal-back")
        self.assertEqual(event["environment"], settings.RESILIENT_LOGGER["environment"])
        self.assertEqual(event["operation"], "READ")
        self.assertEqual(event["message"], "Dependants listed")
        self.assertEqual(event["actor"], {"role": "USER", "uuid": str(self.user.uuid), "ip_address": "10.0.0.1"})
        self.assertEqual(event["target"], {"object_ids": [str(ids[0])], "path": "/vtj/dependants/"})
        extra = event["extra"]
        assert extra is not None
        self.assertEqual(extra["status"], "SUCCESS")
        self.assertEqual(extra["target_type"], "dependant")
        self.assertEqual(extra["source_pk"], entry.pk)


class DependantsViewAuditTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(uuid=uuid.uuid4(), national_identification_number=GUARDIAN_SSN, helsinki_profile_id=uuid.uuid4())
        self.client.force_authenticate(self.user)
        guardian = Guardian.objects.create(ssn=GUARDIAN_SSN)
        self.dependants = [Dependant.objects.create(ssn=ssn) for ssn in (CHILD_SSN, SIBLING_SSN)]
        for dependant in self.dependants:
            dependant.guardians.add(guardian)

    def test_listing_dependants_writes_one_entry(self):
        response = self.client.get(reverse("vtj:dependants"), headers={"X-Request-ID": "trace-123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        context = only_entry(self).context
        self.assertEqual(context["operation"], "READ")
        self.assertEqual(context["actor"]["role"], "USER")
        self.assertEqual(context["actor"]["uuid"], str(self.user.uuid))
        self.assertEqual(set(context["target"]["object_ids"]), {str(dependant.pk) for dependant in self.dependants})
        self.assertEqual(context["target_type"], "dependant")
        self.assertEqual(context["request_id"], "trace-123")

    def test_entry_has_no_henkilotunnus(self):
        self.client.get(reverse("vtj:dependants"))

        serialized = json.dumps(only_entry(self).context)
        for ssn in (GUARDIAN_SSN, CHILD_SSN, SIBLING_SSN):
            self.assertNotIn(ssn, serialized)

    def test_failed_audit_write_fails_the_request(self):
        with mock.patch(CREATE_ENTRY, side_effect=RuntimeError("database down")), self.assertRaises(RuntimeError):
            self.client.get(reverse("vtj:dependants"))
