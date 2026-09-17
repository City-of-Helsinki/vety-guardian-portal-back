#!/usr/bin/env python3
"""
Standalone mock server for the City of Helsinki VTJ Gateway contract
(HenkilonTunnuskysely), for local development when you don't yet have real
Gateway/DVV access.

Run it as its own process:

    uv run python -m vtj.testing.mock_server            # listens on :8000
    uv run python -m vtj.testing.mock_server 8080       # or a custom port

Then point your Django settings at it:

    VTJ_HEL_ENDPOINT = "http://localhost:8080/api/HenkilonTunnuskysely"

NOTE ON FIELD NAMES: the wire-format field names below (Henkilotunnus,
SoSoNimi, Loppukayttaja, Paluukoodi, Asiakasinfo, Henkilo, Huoltaja,
Huollettava, Turvakielto, TurvakieltoTieto, NykyinenSukunimi, Sukunimi,
NykyisetEtunimet, Etunimet, Syntymaaika, ...) are names
required by the VTJ/Palveluväylä interface and its underlying WSDL.
("HUOLLETTAVA-HUOLTAJAT_Vastaus.xsd" and "HUOLTAJA-HUOLLETTAVAT_Vastaus.xsd",
see /vtj/schemas/)

https://dvv.fi/vtjkysely-rajapinta-julkiselle-sektorille
https://liityntakatalogi.suomi.fi/dataset/vtjrajapinta


This script is deliberately dependency-free (standard library only), so
it needs no extra `pip install` beyond Python itself.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PATH = "/api/HenkilonTunnuskysely"

# A special identity code that always simulates "person not found", so you
# can exercise your application's error handling on demand.
NOT_FOUND_SSN = "010101-0199"

# Canned people, keyed by Henkilotunnus. Add more entries/scenarios here as
# your application needs to exercise them (e.g. a guardian with several
# dependants, a dependant with two guardians, someone with an active
# Turvakielto, etc.) - this is a normal Python dict, so it's easy to extend
# or even load from a JSON fixture file if it grows large.
PEOPLE: dict[str, dict] = {
    "010101-0101": {
        "name": {"NykyinenSukunimi": {"Sukunimi": "Example"}, "NykyisetEtunimet": {"Etunimet": "OtherParent"}},
        "address": {"LahiosoiteS": "Mannerheimintie 10 A 1", "Postinumero": "00100", "PostitoimipaikkaS": "Helsinki"},
        "Huollettava": [
            {
                "Henkilotunnus": "010115-999X",
                "Syntymaaika": "20150101",
                "NykyinenSukunimi": {"Sukunimi": "Example"},
                "NykyisetEtunimet": {"Etunimet": "Child"},
            },
        ],
        "Turvakielto": {"TurvakieltoTieto": "0"},
    },
    # A guardian with two dependants - queried with SoSoNimi=HUOLTAJA-HUOLLETTAVAT.
    "010170-999X": {
        "name": {"NykyinenSukunimi": {"Sukunimi": "Example"}, "NykyisetEtunimet": {"Etunimet": "Parent"}},
        "address": {"LahiosoiteS": "Runeberginkatu 5 B 12", "Postinumero": "00100", "PostitoimipaikkaS": "Helsinki"},
        "Huollettava": [
            {
                "Henkilotunnus": "010115-999X",
                "Syntymaaika": "20150101",
                "NykyinenSukunimi": {"Sukunimi": "Example"},
                "NykyisetEtunimet": {"Etunimet": "Child"},
            },
            {
                "Henkilotunnus": "010216-998X",
                "Syntymaaika": "20160201",
                "NykyinenSukunimi": {"Sukunimi": "Example"},
                "NykyisetEtunimet": {"Etunimet": "OtherChild"},
            },
        ],
        "Huoltaja": [],
        "Turvakielto": {"TurvakieltoTieto": "0"},
    },
    # A person with an active address-protection flag, to exercise
    # has_address_protection().
    "010101-0102": {
        "name": {"NykyinenSukunimi": {"Sukunimi": "Protected"}, "NykyisetEtunimet": {"Etunimet": "Person"}},
        "Huollettava": [],
        "Huoltaja": [],
        "Turvakielto": {"TurvakieltoTieto": "1"},
    },
    # The two dependants referenced above (010115-999X, 010216-998X) also
    # get their OWN top-level entries, so SoSoNimi=HUOLLETTAVA-HUOLTAJAT
    # can resolve them. A minor is modelled as sharing its guardian's
    # address and having no dependants of its own.
    "010115-999X": {
        "name": {"NykyinenSukunimi": {"Sukunimi": "Example"}, "NykyisetEtunimet": {"Etunimet": "Child"}},
        # Shares an address with guardian "010101-0101" above.
        "address": {"LahiosoiteS": "Mannerheimintie 10 A 1", "Postinumero": "00100", "PostitoimipaikkaS": "Helsinki"},
        "Huollettava": [],
        # Has two guardians - both "010101-0101" and "010170-999X" already
        # list this ssn in their own Huollettava above; this is the
        # reciprocal, ward-side view of that same relationship.
        "Huoltaja": [
            {
                "Henkilotunnus": "010101-0101",
                "Syntymaaika": "19850505",
                "NykyinenSukunimi": {"Sukunimi": "Example"},
                "NykyisetEtunimet": {"Etunimet": "OtherParent"},
            },
            {
                "Henkilotunnus": "010170-999X",
                "Syntymaaika": "19700101",
                "NykyinenSukunimi": {"Sukunimi": "Example"},
                "NykyisetEtunimet": {"Etunimet": "Parent"},
            },
        ],
        "Turvakielto": {"TurvakieltoTieto": "0"},
    },
    "010216-998X": {
        "name": {"NykyinenSukunimi": {"Sukunimi": "Example"}, "NykyisetEtunimet": {"Etunimet": "OtherChild"}},
        # Shares an address with its only guardian, "010170-999X" above.
        "address": {"LahiosoiteS": "Runeberginkatu 5 B 12", "Postinumero": "00100", "PostitoimipaikkaS": "Helsinki"},
        "Huollettava": [],
        "Huoltaja": [
            {
                "Henkilotunnus": "010170-999X",
                "Syntymaaika": "19700101",
                "NykyinenSukunimi": {"Sukunimi": "Example"},
                "NykyisetEtunimet": {"Etunimet": "Parent"},
            },
        ],
        "Turvakielto": {"TurvakieltoTieto": "0"},
    },
}


def _envelope(payload: dict) -> dict:
    """
    Wraps a `{"Paluukoodi": ..., "Henkilo": ...}` payload in the
    `VTJHenkiloVastaussanoma` document element the real XSDs define as the
    response root. This mock's own diagnostic
    errors (bad JSON, missing Loppukayttaja, wrong path) are NOT part of
    the VTJ contract, so they're sent as plain `{"error": ...}` bodies,
    unwrapped.
    """
    return {"VTJHenkiloVastaussanoma": payload}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != PATH:
            self._send_json(404, {"error": f"no such endpoint, expected {PATH}"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        ssn = body.get("Henkilotunnus")
        sosonimi = body.get("SoSoNimi")
        end_user = body.get("Loppukayttaja")

        # Loppukayttaja is mandatory in the real interface - fail loudly
        # here too, so tests/local runs catch a missing value early
        # instead of only discovering it against the real Gateway.
        if not end_user:
            self._send_json(400, {"error": "Loppukayttaja is required"})
            return

        if ssn == NOT_FOUND_SSN or ssn not in PEOPLE:
            self._send_json(200, _envelope({"Paluukoodi": {"koodi": "0001", "value": "Person not found"}}))
            return

        person = PEOPLE[ssn]
        henkilo = {
            "Henkilotunnus": ssn,
            **person["name"],
            "Turvakielto": person["Turvakielto"],
        }
        # Address lives on the top-level Henkilo record regardless of which
        # SoSoNimi was queried (see the comment above PEOPLE) - included
        # unconditionally here, and simply absent for a person with no
        # "address" key (i.e. an active Turvakielto).
        if person.get("address"):
            henkilo["VakinainenKotimainenLahiosoite"] = person["address"]
        if sosonimi == "HUOLTAJA-HUOLLETTAVAT":
            henkilo["Huollettava"] = person["Huollettava"]
        elif sosonimi == "HUOLLETTAVA-HUOLTAJAT":
            henkilo["Huoltaja"] = person["Huoltaja"]
        elif sosonimi != "PERUSSANOMA 1":
            self._send_json(400, {"error": f"unrecognized SoSoNimi: {sosonimi!r}"})
            return

        self._send_json(200, _envelope({"Paluukoodi": {"koodi": "0000", "value": "OK"}, "Henkilo": henkilo}))

    def _send_json(self, status: int, data: dict) -> None:
        # print("[vtj-mock]", data)
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        print("[vtj-mock]", format % args)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("localhost", port), Handler)
    print(f"VTJ mock server listening on http://localhost:{port}{PATH}")
    print(f"Known test identity codes: {', '.join(PEOPLE)} (plus {NOT_FOUND_SSN} for 'not found')")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
