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
import threading
from pathlib import Path
from typing import Any

from lifx.color import HSBK

_LOGGER = logging.getLogger(__name__)

# Locks serialising read-modify-write cycles per state file, keyed on the
# resolved path so every spelling of one file shares a lock. Bounded by the
# number of distinct state files an application opens.
#
# These are ``threading.Lock`` rather than ``asyncio.Lock`` because the file
# I/O runs in worker threads: an asyncio.Lock binds to whichever event loop
# first contends for it, so two loops sharing a file would deadlock, and it
# would be released the instant a pending ``asyncio.to_thread`` is cancelled —
# while the worker thread carried on writing. Taking the lock inside the
# thread avoids both. ``_STATE_FILE_LOCKS_GUARD`` makes the get-or-create
# atomic; without it two threads can install two locks for one file.
_STATE_FILE_LOCKS_GUARD = threading.Lock()
_STATE_FILE_LOCKS: dict[str, threading.Lock] = {}


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


def _resolve_state_path(path: str | Path) -> Path:
    """Normalise a state file path so every spelling maps to one lock.

    Expands ``~`` and resolves relative segments and symlinks. Case-only
    differences on case-insensitive filesystems are left alone: folding them
    would be wrong on a case-sensitive one.

    Args:
        path: State file path as supplied by the caller

    Returns:
        The resolved path
    """
    return Path(path).expanduser().resolve()


def _state_file_lock(path: Path) -> threading.Lock:
    """Get the lock guarding a state file.

    Several devices can share one state file, and saving is a read-merge-write
    cycle. That I/O runs in worker threads, so without this lock two saves
    could interleave and drop one device's entry — running on the event loop
    used to serialise them for free.

    Args:
        path: Resolved path to the state file

    Returns:
        The lock guarding that path
    """
    key = str(path)
    with _STATE_FILE_LOCKS_GUARD:
        lock = _STATE_FILE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _STATE_FILE_LOCKS[key] = lock
        return lock


def read_state_file(state_file: str | Path) -> tuple[bool, Any]:
    """Read and parse the state file. Blocking — call via asyncio.to_thread.

    Takes the file's lock so a read cannot observe a half-finished merge.

    Args:
        state_file: Path to the JSON state file; resolved here

    Returns:
        ``(exists, contents)``. The flag distinguishes an absent file from one
        that parses to JSON ``null``, which is corruption rather than absence.
    """
    resolved = _resolve_state_path(state_file)
    with _state_file_lock(resolved):
        if not resolved.exists():
            return False, None

        with resolved.open("r") as f:
            return True, json.load(f)


def write_state_file(
    state_file: str | Path, serial: str, device_state: dict[str, Any]
) -> None:
    """Merge one device's state into the state file and write it back.

    Blocking — call via asyncio.to_thread. Takes the file's lock for the whole
    read-merge-write cycle, so devices sharing a file cannot drop each other's
    entries. The lock is process-local: it does not coordinate with a separate
    process pointed at the same file.

    The on-disk entry is merged rather than replaced so absent in-memory values
    (e.g. state that failed to load in ``__aenter__``) are not clobbered.

    Args:
        state_file: Path to the JSON state file; resolved here
        serial: Serial number of the device whose entry is being updated
        device_state: Serialisable state to merge into that device's entry

    Raises:
        ValueError: If the existing file does not contain a JSON object, which
            would otherwise be silently overwritten along with every device's
            stored state
    """
    resolved = _resolve_state_path(state_file)
    with _state_file_lock(resolved):
        if resolved.exists():
            with resolved.open("r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(
                    f"State file {resolved} does not contain a JSON object "
                    f"(found {type(data).__name__}); refusing to overwrite it"
                )
        else:
            data = {}

        entry = data.get(serial, {})
        entry.update(device_state)
        data[serial] = entry

        # Ensure directory exists
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically: dump to a temp file in the same directory, then
        # replace, so a crash mid-write cannot leave a truncated file that
        # loses every device's stored state
        fd, tmp = tempfile.mkstemp(dir=resolved.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, resolved)
        except BaseException:
            os.unlink(tmp)
            raise
