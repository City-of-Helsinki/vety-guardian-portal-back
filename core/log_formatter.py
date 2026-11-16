"""
JSON log formatter used by settings.LOGGING (LOG_FORMAT=json).

uWSGI in production doesn't use the "django.server" logger, where the error was first seen (see _safe_serialize).
But any other value in a record's extra that fails to serialize would lose its line the same way, so this is
fixed in the formatter instead of only for runserver.

TODO: The bug is in django-logger-extra's json_serialize. Report it to
https://github.com/City-of-Helsinki/django-logger-extra, and once it's fixed there, remove this module and use
logger_extra.formatter.JSONFormatter in settings.LOGGING again.
"""

from __future__ import annotations

import json
import logging

from django.utils import timezone
from logger_extra.formatter import JSONFormatter as LoggerExtraJSONFormatter
from logger_extra.utils import json_serialize, parse_log_record_extra


def _safe_serialize(value: object) -> object:
    """
    logger_extra's json_serialize, but a value that can't be serialized is logged as its type name instead of
    failing the whole line. For example, runserver's "django.server" request lines pass the client socket in
    extra["request"], and json_serialize calls getpeername() on it after the client has disconnected (OSError).
    """
    try:
        return json_serialize(value)
    except Exception:  # noqa: BLE001 - logging must not fail, whatever the value's __str__ or accessors raise
        return f"<{type(value).__name__}>"


class JSONFormatter(LoggerExtraJSONFormatter):
    """logger_extra.formatter.JSONFormatter with the same output, using _safe_serialize."""

    def format(self, record: logging.LogRecord) -> str:
        extra = parse_log_record_extra(record)
        extra.pop("response", None)

        if record.exc_info:
            extra["exc_info"] = self.formatException(record.exc_info)

        formatted = {
            "message": record.getMessage(),
            "level": record.levelname,
            "name": record.name,
            "time": timezone.now().isoformat(),
            "context": extra,
        }

        return json.dumps(formatted, default=_safe_serialize)
