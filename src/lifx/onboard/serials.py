"""Serial number helpers for onboarding."""

from __future__ import annotations

import re

from lifx.protocol.models import LIFX_OUI, Serial

__all__ = ["LIFX_OUI", "parse_serial", "serial_from_softap_ssid"]

_FULL_PATTERN = re.compile(r"[0-9a-fA-F]{12}")
_SEPARATORS = str.maketrans("", "", ":- ")

#: Module-level alias of :meth:`lifx.protocol.models.Serial.from_softap_ssid`.
serial_from_softap_ssid = Serial.from_softap_ssid


def parse_serial(text: str | Serial) -> Serial:
    """Turn a serial, a six-hex suffix or a ``Serial`` into a ``Serial``.

    Accepts twelve hex characters, or exactly six (the suffix, with the LIFX
    OUI prepended). ``:``, ``-`` and space separators are ignored and case is
    not significant. A ``Serial`` is returned unchanged.

    Raises:
        ValueError: If the text is neither form.
        TypeError: If text is not a string or ``Serial``.
    """
    if isinstance(text, Serial):
        return text
    if not isinstance(text, str):  # type: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"Serial must be a string, got {type(text).__name__}")
    bare = text.translate(_SEPARATORS)
    if _FULL_PATTERN.fullmatch(bare):
        return Serial.from_string(bare)
    return Serial.from_suffix(bare)
