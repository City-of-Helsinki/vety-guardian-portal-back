"""
OAuth2 client-credentials access token for the City of Helsinki API Gateway.

The token is fetched from VTJ_HEL_TOKEN_URL with HTTP Basic auth
(VTJ_HEL_CLIENT_ID:VTJ_HEL_CLIENT_SECRET) and cached in-process until shortly
before it expires. When VTJ_HEL_CLIENT_ID is not set (e.g. the in-app mock),
no token is used.
"""

from __future__ import annotations

import logging
import threading
import time

import requests
from django.conf import settings

from .exceptions import VTJAuthenticationError, VTJConnectionError

logger = logging.getLogger("vety-guardian-portal-back")

SCOPE = "vtj-api.persons:read"
# Refresh this many seconds before the token actually expires.
EXPIRY_MARGIN_SECONDS = 30

_lock = threading.Lock()
_token: str | None = None
_expires_at: float = 0.0


def get_access_token(force_refresh: bool = False) -> str | None:
    """Returns a valid access token, or None when token auth is not configured."""
    global _token, _expires_at

    if not settings.VTJ_HEL_CLIENT_ID:
        return None

    with _lock:
        if not force_refresh and _token and time.monotonic() < _expires_at:
            return _token
        _token, expires_in = _fetch_token()
        _expires_at = time.monotonic() + max(expires_in - EXPIRY_MARGIN_SECONDS, 0)
        return _token


def clear_cached_token() -> None:
    global _token, _expires_at
    with _lock:
        _token = None
        _expires_at = 0.0


def _fetch_token() -> tuple[str, int]:
    try:
        response = requests.post(
            settings.VTJ_HEL_TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": SCOPE},
            auth=(settings.VTJ_HEL_CLIENT_ID, settings.VTJ_HEL_CLIENT_SECRET),
            timeout=settings.VTJ_HEL_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        logger.error("VTJ token endpoint connection error")
        raise VTJConnectionError(str(exc)) from exc

    if response.status_code in (400, 401, 403):
        logger.error(f"VTJ token endpoint rejected the client credentials (HTTP {response.status_code})")
        raise VTJAuthenticationError(f"Token endpoint returned HTTP {response.status_code}")
    if not response.ok:
        logger.error(f"VTJ token endpoint HTTP error {response.status_code}")
        raise VTJConnectionError(f"Token endpoint returned HTTP {response.status_code}")

    try:
        data = response.json()
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 60))
    except (ValueError, KeyError, TypeError) as exc:
        logger.error("VTJ token endpoint response was not in the expected format")
        raise VTJConnectionError("Unexpected token response format") from exc

    return token, expires_in
