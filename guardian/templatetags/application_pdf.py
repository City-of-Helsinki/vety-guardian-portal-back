"""
Template tags for guardian/application_pdf.html. They mirror the frontend's `t()` and components, so the template
reads like Esikatselu.tsx. The template context must contain the Translator as `t` (see guardian/pdf.py).
"""

from __future__ import annotations

from typing import Any

from django import template
from django.utils.safestring import SafeString, mark_safe
from markdown_it import MarkdownIt

register = template.Library()

# CommonMark + tables like react-markdown with remark-gfm (MarkdownContent.tsx). Raw HTML is escaped.
_markdown = MarkdownIt("commonmark", {"html": False}).enable("table")

# Same as EMPTY_VALUE in vety-guardian-portal-front/src/components/summary/LabelValue.tsx
EMPTY_VALUE = "–"


@register.simple_tag(takes_context=True)
def t(context: template.Context, key: str) -> str:
    return context["t"](key)


@register.simple_tag(takes_context=True)
def t_markdown(context: template.Context, key: str) -> SafeString:
    """Like <MarkdownContent>{t(key)}</MarkdownContent>. The texts come from our own Locize project."""
    return mark_safe(_markdown.render(context["t"](key)))


@register.inclusion_tag("guardian/_label_value.html", takes_context=True)
def label_value(context: template.Context, label_key: str, value: Any, testid: str = "") -> dict[str, Any]:
    """Like <LabelValue label={t(label_key)} value={value} />: one line per value, "–" when there are none."""
    values = [line for line in (value if isinstance(value, list) else [value]) if line]
    return {"label": context["t"](label_key), "values": values or [EMPTY_VALUE], "testid": testid}
