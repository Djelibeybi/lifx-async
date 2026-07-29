"""Shared helpers for component-based light state.

Ceiling and Mirror lights both split their matrix into logical components
whose colours are tracked in memory and optionally persisted to a JSON file
keyed by device serial. This module holds the pieces both device classes need
so the persistence format and comparison rules stay identical between them.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from lifx.color import HSBK

_LOGGER = logging.getLogger(__name__)


def hsk_matches(stored: HSBK, current: HSBK) -> bool:
    """Compare hue/saturation/kelvin at uint16 (wire) granularity.

    Brightness is intentionally ignored. Comparing the decoded uint16 values
    rather than the raw floats keeps stored-state validity stable across a
    protocol round-trip, which exposes slightly different raw H/S/B floats for
    the same wire representation.

    Args:
        stored: Previously stored colour
        current: Colour currently reported by the device

    Returns:
        True if hue, saturation and kelvin match on the wire
    """
    sp = stored.to_protocol()
    cp = current.to_protocol()
    return (
        sp.hue == cp.hue and sp.saturation == cp.saturation and sp.kelvin == cp.kelvin
    )


def color_as_dict(color: HSBK | None) -> dict[str, float | int] | None:
    """Expand an optional HSBK for serialisation, preserving None.

    Args:
        color: Colour to expand, or None

    Returns:
        Expanded colour mapping, or None
    """
    return None if color is None else color.as_dict


def colors_as_dict(
    colors: list[HSBK] | None,
) -> list[dict[str, float | int]] | None:
    """Expand an optional list of HSBK for serialisation, preserving None.

    Args:
        colors: Colours to expand, or None

    Returns:
        List of expanded colour mappings, or None
    """
    return None if colors is None else [color.as_dict for color in colors]


def zones_as_dict(zones: slice) -> dict[str, int | None]:
    """Expand a zone slice into a serialisable mapping.

    Component layouts define zones as ``slice(start, stop)``, which leaves
    ``slice.step`` set to None even though it steps by one, so the step is
    normalised to 1 here.

    Args:
        zones: Slice describing a component's zones

    Returns:
        Mapping with start, stop and step keys
    """
    return {
        "start": zones.start,
        "stop": zones.stop,
        "step": 1 if zones.step is None else zones.step,
    }


def decode_color(data: dict[str, Any]) -> HSBK:
    """Rebuild an HSBK from its persisted mapping.

    Args:
        data: Mapping with hue, saturation, brightness and kelvin keys

    Returns:
        HSBK instance
    """
    return HSBK(
        hue=data["hue"],
        saturation=data["saturation"],
        brightness=data["brightness"],
        kelvin=data["kelvin"],
    )


def encode_color(color: HSBK) -> dict[str, float | int]:
    """Reduce an HSBK to its persisted mapping.

    Args:
        color: Colour to encode

    Returns:
        Mapping with hue, saturation, brightness and kelvin keys
    """
    return {
        "hue": color.hue,
        "saturation": color.saturation,
        "brightness": color.brightness,
        "kelvin": color.kelvin,
    }


def read_state_document(state_file: str) -> dict[str, Any]:
    """Read the whole state document from disk.

    Args:
        state_file: Path to the JSON state file

    Returns:
        Parsed document, or an empty dict if the file does not exist
    """
    state_path = Path(state_file).expanduser()
    if not state_path.exists():
        _LOGGER.debug("State file does not exist: %s", state_path)
        return {}

    with state_path.open("r") as f:
        document: dict[str, Any] = json.load(f)

    return document


def write_state_document(state_file: str, document: dict[str, Any]) -> None:
    """Write the whole state document to disk atomically.

    Dumps to a temporary file in the same directory and then replaces the
    target, so a crash mid-write cannot leave a truncated file that loses every
    device's stored state.

    Args:
        state_file: Path to the JSON state file
        document: Document to write
    """
    state_path = Path(state_file).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=state_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(document, f, indent=2)
        os.replace(tmp, state_path)
    except BaseException:
        os.unlink(tmp)
        raise
