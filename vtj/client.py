"""
VTJ query via the City of Helsinki API Gateway's HenkilonTunnuskysely
interface.

NOTE ON FIELD NAMES: the wire-format field names below (Henkilotunnus,
SoSoNimi, Loppukayttaja, Paluukoodi, Asiakasinfo, Henkilo, Huoltaja,
Huollettava, Turvakielto, TurvakieltoTieto, NykyinenSukunimi, Sukunimi,
NykyisetEtunimet, Etunimet, Syntymaaika, ...) are the field names
required by the VTJ/Palveluväylä interface and its underlying WSDL.
("HUOLLETTAVA-HUOLTAJAT_Vastaus.xsd" and "HUOLTAJA-HUOLLETTAVAT_Vastaus.xsd",
see /vtj_testing/schemas/)

https://dvv.fi/vtjkysely-rajapinta-julkiselle-sektorille
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

from .exceptions import VTJAuthenticationError, VTJConnectionError, VTJParameterError, VTJResponseError
from .vtj_types import Henkilo, Huollettava, Huoltaja, ensure_list

logger = logging.getLogger("vety-guardian-portal-back")

SOSONIMI_BASIC = "PERUSSANOMA 1"
SOSONIMI_GET_DEPENDANTS = "HUOLTAJA-HUOLLETTAVAT"  # query person as guardian -> returns Huollettava list (DEPENDANTS)
SOSONIMI_GET_GUARDIANS = "HUOLLETTAVA-HUOLTAJAT"  # query person as ward -> returns Huoltaja list (GUARDIANS)


def _call(ssn: str, sosonimi: str, end_user: str) -> dict:
    """
    Calls the City of Helsinki API Gateway's HenkilonTunnuskysely
    interface.

    :param ssn: the Finnish personal identity code (Henkilotunnus) of the person to query
    :param sosonimi: SOSONIMI_BASIC / SOSONIMI_GET_DEPENDANTS / SOSONIMI_GET_GUARDIANS
    :param end_user: the identifier of the natural person (e.g. a
        Helsinki-profile ID) on whose behalf the query is made -
        MANDATORY for traceability/audit logging. Never leave it empty
        and never use the system's own technical identifier.
    """
    if not end_user:
        logger.error(f'VTJ query "Loppukayttaja" can not be empty, end_user={end_user}')
        raise VTJParameterError("VTJ query parameter error")

    payload = {
        "Henkilotunnus": ssn,
        "SoSoNimi": sosonimi,
        "Loppukayttaja": end_user,
    }
    headers = {"Content-Type": "application/json"}

    secret_header = getattr(settings, "VTJ_HEL_SHARED_SECRET_HEADER", None)
    if secret_header:
        headers[secret_header] = settings.VTJ_HEL_SHARED_SECRET

    # logger.info("VTJ query ssn=%s***, SoSoNimi=%s, end_user=%s", ssn[:6], sosonimi, end_user)
    logger.info(f"VTJ query SoSoNimi={sosonimi}, end_user={end_user}")

    try:
        response = requests.post(
            settings.VTJ_HEL_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=getattr(settings, "VTJ_HEL_TIMEOUT", 10),
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (401, 403):
            logger.error("VTJ gateway rejected the call (authentication/authorization)")
            raise VTJAuthenticationError(f"Gateway returned HTTP {status}") from exc
        logger.error("VTJ gateway HTTP error")
        raise VTJConnectionError(str(exc)) from exc
    except requests.exceptions.RequestException as exc:
        logger.error("VTJ connection error (gateway)")
        raise VTJConnectionError(str(exc)) from exc

    try:
        data = response.json()
    except ValueError as exc:
        logger.error("VTJ gateway response was not JSON - unexpected format")
        raise VTJConnectionError("Unexpected response format (not JSON)") from exc

    data = _unwrap_envelope(data)
    _check_return_code(data)
    return data


def _unwrap_envelope(data: dict) -> dict:
    """
    Per the XSDs, a response's document (root) element is
    `VTJHenkiloVastaussanoma`, wrapping `Paluukoodi`/`Henkilo`
    Unwraps that key if present;
    otherwise assumes the Gateway's JSON conversion already stripped it and
    returns `data` unchanged, so this works either way until you've
    confirmed which one the real Gateway actually does.
    """
    envelope = data.get("VTJHenkiloVastaussanoma")
    return envelope if isinstance(envelope, dict) else data


def _check_return_code(data: dict) -> None:
    """
    Per the XSD, Paluukoodi is <Paluukoodi koodi="0000">text</Paluukoodi> -
    i.e. the code is an ATTRIBUTE, not the element's text content.
    `_extract_code_value()` tries to recognize the most common JSON
    conversions - refine as needed once you see a real response.
    """
    code = _extract_code_value(data.get("Paluukoodi"))
    if code and code not in {"0000"}:
        message = _extract_error_message(data.get("Paluukoodi"))
        raise VTJResponseError(code, message=message)


def _extract_code_value(return_code: Any) -> str | None:
    """
    Extracts the return code regardless of how the XML attribute 'koodi'
    was converted to JSON

    TODO: VERIFY THE ACTUAL SHAPE against the first real response and trim the unused alternatives.
    """
    if return_code is None:
        return None
    if isinstance(return_code, str):
        return return_code
    if isinstance(return_code, dict):
        for key in ("koodi", "@koodi", "Koodi"):
            if key in return_code:
                return return_code[key]
    return None


def _extract_error_message(return_code: Any) -> str:
    if return_code is None:
        return ""
    if isinstance(return_code, dict):
        key = "value"
        if key in return_code:
            return return_code[key]
    return ""


def get_basic_info(ssn: str, end_user: str) -> Henkilo:
    """SoSoNimi = 'PERUSSANOMA 1' - matches the public PERUSLT1 basic data package."""
    data = _call(ssn, SOSONIMI_BASIC, end_user)
    return Henkilo.from_response(ssn, data.get("Henkilo") or {})


def get_dependants(ssn: str, end_user: str) -> tuple[Henkilo, list[Huollettava]]:
    """Queries the person as a guardian (SoSoNimi='HUOLTAJA-HUOLLETTAVAT')."""
    data = _call(ssn, SOSONIMI_GET_DEPENDANTS, end_user)
    person = data.get("Henkilo") or {}
    dependants = [Huollettava.from_row(row) for row in ensure_list(person.get("Huollettava"))]
    return Henkilo.from_response(ssn, person), dependants


def get_guardians(ssn: str, end_user: str) -> tuple[Henkilo, list[Huoltaja]]:
    """Queries the person as a ward (SoSoNimi='HUOLLETTAVA-HUOLTAJAT')."""
    data = _call(ssn, SOSONIMI_GET_GUARDIANS, end_user)
    person = data.get("Henkilo") or {}
    guardians = [Huoltaja.from_row(row) for row in ensure_list(person.get("Huoltaja"))]
    return Henkilo.from_response(ssn, person), guardians
