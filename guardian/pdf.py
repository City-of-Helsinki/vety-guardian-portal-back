"""
Renders the application as a PDF with WeasyPrint, looking like the frontend's Esikatselu step
(vety-guardian-portal-front/src/components/application-form/steps/Esikatselu.tsx).

The texts come from Locize (see translations.py), the styles and logo from guardian/static/guardian/pdf/.
Everything is inlined into the HTML, and WeasyPrint may only read data: URLs, so it never touches files or the network.
"""

from __future__ import annotations

import base64
from pathlib import Path

from django.template.loader import render_to_string
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from .models.application import PreschoolApplication
from .translations import Translator

ASSETS_DIR = Path(__file__).resolve().parent / "static" / "guardian" / "pdf"

# Same as the site header (vety-guardian-portal-front/src/App.tsx): Swedish logo for sv, Finnish otherwise.
# See guardian/static/guardian/pdf/README.md for where to download the latest logo files.
LOGOS = {"sv": "helsinki-sv-m-black.svg"}
DEFAULT_LOGO = "helsinki-fi-m-black.svg"


def _logo_data_uri(lang: str) -> str:
    svg = (ASSETS_DIR / LOGOS.get(lang, DEFAULT_LOGO)).read_bytes()
    return f"data:image/svg+xml;base64,{base64.b64encode(svg).decode()}"


def render_application_html(application: PreschoolApplication, lang: str) -> str:
    t = Translator(lang)

    # Mirrors the `laajuus` list in Esikatselu.tsx.
    laajuus = [t(f"vakaOptions.{value}") for value in (application.hoidon_tarve, application.palvelun_tarve) if value]
    arkipoissaolot = str(application.arkipoissaolot_lkm) if application.taydentava_varhaiskasvatus and application.arkipoissaolot_lkm is not None else None

    context = {
        "t": t,
        "lang": lang,
        "application": application,
        "laajuus": laajuus,
        "arkipoissaolot": arkipoissaolot,
        "css": (ASSETS_DIR / "application_pdf.css").read_text(encoding="utf-8"),
        "logo": _logo_data_uri(lang),
    }
    return render_to_string("guardian/application_pdf.html", context)


def render_application_pdf(application: PreschoolApplication, lang: str) -> bytes:
    html = render_application_html(application, lang)
    return HTML(string=html, url_fetcher=URLFetcher(allowed_protocols={"data"})).write_pdf()  # pyright: ignore[reportReturnType]
