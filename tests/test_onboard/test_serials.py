"""Tests for lifx.onboard serial helpers."""

from __future__ import annotations

import pytest

from lifx.onboard import LIFX_OUI, parse_serial, serial_from_softap_ssid
from lifx.protocol import models
from lifx.protocol.models import Serial

EXPECTED = Serial.from_string("d073d58274eb")


def test_oui_value() -> None:
    assert LIFX_OUI == b"\xd0\x73\xd5"
    assert LIFX_OUI is models.LIFX_OUI


@pytest.mark.parametrize(
    "text",
    [
        "d073d58274eb",
        "D073D58274EB",
        "d0:73:d5:82:74:eb",
        "d0-73-d5-82-74-eb",
        "d0 73 d5 82 74 eb",
        "8274eb",
        "8274EB",
        "82:74:eb",
        "82-74-eb",
        "82 74 eb",
    ],
)
def test_parse_serial_accepts(text: str) -> None:
    assert parse_serial(text) == EXPECTED


def test_parse_serial_passes_serial_through() -> None:
    assert parse_serial(EXPECTED) is EXPECTED


@pytest.mark.parametrize(
    "text",
    [
        "",
        "8274e",
        "8274ebc",
        "d073d58274e",
        "d073d58274eb0",
        "zzzzzz",
        "d073d58274ez",
        "82\t74eb",
        "8274eb\n",
    ],
)
def test_parse_serial_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        parse_serial(text)


def test_parse_serial_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        parse_serial(None)  # type: ignore[arg-type]


def test_serial_from_softap_ssid_alias() -> None:
    assert serial_from_softap_ssid("LIFX Candle Color 8274eb") == EXPECTED
    with pytest.raises(ValueError):
        serial_from_softap_ssid("Neighbour4C0A17")
