"""
Reads the frontend's translations from the Locize CDN, so the application PDF uses the same texts as the site.

The frontend loads the same namespace with i18next-locize-backend (vety-guardian-portal-front/src/i18n/i18n.ts).
Keys are looked up like i18next does: dotted paths ("esikatselu.kieli"), falling back to Finnish.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("vety-guardian-portal-back")

# Keep in sync with SUPPORTED_LANGUAGES in vety-guardian-portal-front/src/i18n/i18n.ts
SUPPORTED_LANGUAGES = ("fi", "sv", "en")
FALLBACK_LANGUAGE = "fi"
NAMESPACE = "lomake"
CACHE_TIMEOUT = 60 * 60


class TranslationError(Exception):
    pass


def get_translations(lang: str) -> dict[str, Any]:
    """Returns the `lomake` namespace for `lang` from Locize. Successful responses are cached for an hour."""
    cache_key = f"locize:{settings.LOCIZE_VERSION}:{lang}:{NAMESPACE}"
    translations = cache.get(cache_key)
    if translations is not None:
        return translations

    url = f"{settings.LOCIZE_CDN_URL}/{settings.LOCIZE_PROJECT_ID}/{settings.LOCIZE_VERSION}/{lang}/{NAMESPACE}"
    try:
        response = requests.get(url, timeout=settings.LOCIZE_TIMEOUT)
        response.raise_for_status()
        translations = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise TranslationError(f"Locize request failed: {exc}") from exc
    if not isinstance(translations, dict):
        raise TranslationError("Locize returned unexpected data")

    cache.set(cache_key, translations, CACHE_TIMEOUT)
    return translations


def _lookup(translations: dict[str, Any], key: str) -> str | None:
    value: Any = translations
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value if isinstance(value, str) and value else None


class Translator:
    """`t(key)` like i18next's: the text in `lang`, else in Finnish, else the key itself."""

    def __init__(self, lang: str) -> None:
        self.lang = lang
        self._translations = get_translations(lang)
        self._fallback = get_translations(FALLBACK_LANGUAGE) if lang != FALLBACK_LANGUAGE else {}

    def __call__(self, key: str) -> str:
        return _lookup(self._translations, key) or _lookup(self._fallback, key) or key
