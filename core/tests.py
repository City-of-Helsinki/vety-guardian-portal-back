import importlib

from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse

import core.urls


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
