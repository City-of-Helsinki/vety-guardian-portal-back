import copy
import importlib
import io
import json
import logging
import logging.config
import socket
import uuid
from unittest import mock

from django.conf import settings
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, path, reverse

import core.urls

logger = logging.getLogger(__name__)


def reload_urls(**overrides: object) -> None:
    """
    Rebuilds core/urls.py with the given settings, which are read at import time (e.g. ADMIN_ENABLED).
    Without overrides, restores the routes for the real settings.
    """
    with override_settings(**overrides):
        importlib.reload(core.urls)
        clear_url_caches()


class AdminRoutingTests(SimpleTestCase):
    """core/urls.py includes the Django admin only when ADMIN_ENABLED is on. Independent of the flag in .env."""

    def setUp(self):
        self.addCleanup(reload_urls)

    def test_not_routed_when_disabled(self):
        reload_urls(ADMIN_ENABLED=False)
        with self.assertRaises(NoReverseMatch):
            reverse("admin:index")
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_routed_when_enabled(self):
        reload_urls(ADMIN_ENABLED=True)
        self.assertEqual(reverse("admin:index"), "/admin/")


class HealthCheckTests(TestCase):
    """The root path and the OpenShift probes (core/views.py) answer GET and HEAD only."""

    URLS = ("/", "/healthz", "/readiness")

    def test_get_and_head_ok(self):
        for url in self.URLS:
            for method in ("get", "head"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 200)

    def test_get_body(self):
        for url in self.URLS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).json(), {"status": "ok"})

    def test_other_methods_not_allowed(self):
        for url in self.URLS:
            for method in ("post", "put", "patch", "delete"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 405)
                    self.assertEqual(response["Allow"], "GET, HEAD")

    def test_readiness_database_unavailable(self):
        with mock.patch("core.views.connections") as connections:
            connections.__getitem__.return_value.cursor.side_effect = DatabaseError("down")
            response = self.client.get("/readiness")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error", "detail": "database unavailable"})


def logging_view(request: HttpRequest) -> JsonResponse:
    logger.warning("hello from a view")
    return JsonResponse({})


urlpatterns = [path("log/", logging_view)]


@override_settings(ROOT_URLCONF=__name__)
class LoggingTests(SimpleTestCase):
    """settings.LOGGING with each LOG_FORMAT, captured from the console handler. Independent of LOG_FORMAT in .env."""

    def configure_logging(self, log_format: str) -> io.StringIO:
        """Applies settings.LOGGING with the given format, writing to a buffer. Restored after the test."""
        stream = io.StringIO()
        config = copy.deepcopy(settings.LOGGING)
        config["handlers"]["console"]["formatter"] = log_format
        config["handlers"]["console"]["stream"] = stream
        logging.config.dictConfig(config)
        self.addCleanup(logging.config.dictConfig, settings.LOGGING)
        return stream

    def lines(self, stream: io.StringIO) -> list[str]:
        return stream.getvalue().splitlines()

    def test_json_line_has_logger_name_and_request_id_from_header(self):
        stream = self.configure_logging("json")
        response = self.client.get("/log/", headers={"X-Request-ID": "trace-123"})

        self.assertEqual(response["X-Request-ID"], "trace-123")
        record = json.loads(self.lines(stream)[-1])
        self.assertEqual(record["message"], "hello from a view")
        self.assertEqual(record["level"], "WARNING")
        self.assertEqual(record["name"], "core.tests")
        self.assertEqual(record["context"]["request_id"], "trace-123")

    def test_request_id_is_generated_without_header(self):
        stream = self.configure_logging("json")
        response = self.client.get("/log/")

        request_id = response["X-Request-ID"]
        uuid.UUID(request_id)
        self.assertEqual(json.loads(self.lines(stream)[-1])["context"]["request_id"], request_id)

    def test_json_exception_stays_on_one_line(self):
        stream = self.configure_logging("json")
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("failed")

        lines = self.lines(stream)
        self.assertEqual(len(lines), 1)
        self.assertIn("ValueError: boom", json.loads(lines[0])["context"]["exc_info"])

    def test_json_unserializable_extra_does_not_drop_the_line(self):
        """runserver passes the client socket as extra["request"]; getpeername() fails once the client is gone."""
        stream = self.configure_logging("json")
        with socket.socket() as unconnected:
            logging.getLogger("django.server").warning('"%s" %s %s', "GET /vtj/dependants/ HTTP/1.1", "200", "287", extra={"request": unconnected})

        record = json.loads(self.lines(stream)[-1])
        self.assertEqual(record["message"], '"GET /vtj/dependants/ HTTP/1.1" 200 287')
        self.assertEqual(record["context"]["request"], "<socket>")

    def test_text_line_has_logger_name_and_request_id(self):
        stream = self.configure_logging("text")
        self.client.get("/log/", headers={"X-Request-ID": "trace-123"})

        line = self.lines(stream)[-1]
        self.assertTrue(line.startswith("WARNING "))
        self.assertIn("[core.tests] [trace-123] hello from a view", line)

    def test_text_line_outside_request(self):
        stream = self.configure_logging("text")
        logger.warning("no request")

        self.assertIn("[core.tests] [-] no request", self.lines(stream)[-1])
