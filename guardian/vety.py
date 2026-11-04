"""
Client for hki-vety's enrollment API, which receives the submitted applications.

PUT {VETY_API_URL}/ilmoittautuneet/{ulkoinen_id} creates or updates the enrollment (ilmoittautuminen)
identified by our application id. The call is idempotent: the whole application is sent each time.
See hki-vety's docs/plans/openapi.yaml (operation tallennaIlmoittautuminen).
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

from .models.application import PreschoolApplication

logger = logging.getLogger("vety-guardian-portal-back")

# The fields hki-vety's IlmoittautuneetLapsetSyoteSerializer accepts. They have the same names here.
ENROLLMENT_FIELDS = [
    "status",
    "henkilotunnus",
    "nimi",
    "syntymavuosi",
    "karttaosoite",
    "kieli",
    "hakenut_ensisijaisesti_yksityiseen",
    "taydentava_varhaiskasvatus",
    "hoidon_tarve",
    "palvelun_tarve",
    "arkipoissaolot_lkm",
    "erityisen_tuen_tarve",
    "laakehoidon_tarve",
    "h1_nimi",
    "h1_osoite",
    "h1_sahkoposti",
    "h1_puhelinnumero",
    "h1_henkilotunnus",
    "h2_nimi",
    "h2_osoite",
    "h2_sahkoposti",
    "h2_puhelinnumero",
    "h2_henkilotunnus",
]


class VetyError(Exception):
    """Sending to hki-vety failed."""


class VetyConfigurationError(VetyError):
    """hki-vety is not configured, or it rejected our token. Retrying other applications won't help."""


class VetyRejectedError(VetyError):
    """hki-vety refused this application (4xx). Sending it again unchanged will fail again."""


def enrollment_payload(application: PreschoolApplication) -> dict[str, Any]:
    payload: dict[str, Any] = {field: getattr(application, field) for field in ENROLLMENT_FIELDS}
    # Checkboxes in the form: null means the guardian never ticked it, i.e. no. hki-vety requires a boolean.
    for field in ("erityisen_tuen_tarve", "laakehoidon_tarve"):
        payload[field] = bool(payload[field])
    payload["submitted_at"] = application.submitted_at.isoformat() if application.submitted_at else None
    aloitus = application.taydentava_varhaiskasvatus_aloitus
    payload["taydentava_varhaiskasvatus_aloitus"] = aloitus.isoformat() if aloitus else None
    return payload


def send_application(application: PreschoolApplication) -> None:
    """PUT the application to hki-vety. Raises VetyError when it wasn't saved there."""
    if not settings.VETY_API_URL or not settings.VETY_API_TOKEN:
        raise VetyConfigurationError("VETY_API_URL and VETY_API_TOKEN must be set")

    url = f"{settings.VETY_API_URL.rstrip('/')}/ilmoittautuneet/{application.pk}"
    try:
        response = requests.put(
            url,
            json=enrollment_payload(application),
            headers={"Authorization": f"Token {settings.VETY_API_TOKEN}"},
            timeout=settings.VETY_API_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise VetyError(f"Connection to hki-vety failed: {exc.__class__.__name__}") from exc

    if response.status_code in (200, 201):
        return
    if response.status_code in (401, 403):
        raise VetyConfigurationError(f"hki-vety rejected the token (HTTP {response.status_code})")
    if 400 <= response.status_code < 500:
        raise VetyRejectedError(f"hki-vety refused the application (HTTP {response.status_code}): {_error_message(response)}")
    raise VetyError(f"hki-vety returned HTTP {response.status_code}")


def _error_message(response: requests.Response) -> str:
    """hki-vety's errors are {"viesti": "..."}; DRF field errors are {"field": ["..."]}."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict) and "viesti" in body:
        return str(body["viesti"])
    return str(body)[:500]
