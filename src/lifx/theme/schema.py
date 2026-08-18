"""The ``data/themes.jsonl`` record contract.

Parsing, validation and palette canonicalisation for the committed theme data
file. Stored colours are ``HSBK``'s own user-facing units: hue in degrees
(0-360), saturation and brightness as a fraction (0-1), kelvin as a wire
integer, never protocol uint16. This is the one implementation of the
contract: the code generator that reads the file and the maintainer tooling
that writes it both import from here, so neither can drift from the other.

Importable but deliberately absent from ``lifx.theme.__all__`` and the published
API docs, so these signatures can change without a major version. Same treatment
as ``lifx.theme.canvas.Canvas``.
"""

from __future__ import annotations

import json
import keyword
import math
from pathlib import Path
from typing import Any

from lifx.const import (
    KELVIN_SATURATED,
    MAX_KELVIN,
    MIN_KELVIN,
)
from lifx.theme.slug import derive_slug

#: Inclusive (min, max) validation range for each user-facing float colour
#: field. Kelvin is validated separately below: it stays a wire integer with
#: its own saturated-zero exemption, not a member of this range table.
_COLOR_FIELD_RANGES: dict[str, tuple[float, float]] = {
    "hue": (0, 360),
    "saturation": (0, 1),
    "brightness": (0, 1),
}

#: Fields every record must carry.
_REQUIRED_FIELDS = frozenset({"slug", "name", "category", "disposition", "colors"})

#: Fields a record may carry in addition to the required set.
_OPTIONAL_FIELDS = frozenset({"aliases", "replaced_by"})

#: Allowed values of a record's authored ``disposition`` field (COMPAT-04).
DISPOSITIONS = frozenset({"lifx-app", "library-only", "deprecated"})

#: Disposition of a rename-alias key. Never authored: an alias lives in its
#: target's ``aliases`` list, and the generator synthesises a record for it
#: so the alias key reports the rename instead of inheriting the target's
#: clean fate. Only the disposition set the emitted module declares is the
#: union of this and ``DISPOSITIONS``.
RENAMED = "renamed"

#: Exact field set of a colour object.
_COLOR_FIELDS = frozenset({"hue", "saturation", "brightness", "kelvin"})


def load_theme_records(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Parse the JSONL data file into (line number, record) pairs.

    The line number travels with each record so every later validation error
    can name the offending line.

    Args:
        path: Path to the JSONL theme data file.

    Returns:
        List of ``(line_number, record)`` pairs in file order.

    Raises:
        RuntimeError: If a line is not valid JSON.
    """
    records: list[tuple[int, dict[str, Any]]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"{path.name} line {line_number}: not valid JSON: {exc}"
                ) from exc
            records.append((line_number, record))
    return records


def validate_key(key: object) -> bool:
    """Canonical-key predicate applied to primary slugs AND aliases.

    A key must be a non-empty ``str``, pure ASCII (``str.isidentifier()``
    alone accepts Unicode identifiers such as ``café``, which the
    deterministic-ASCII rule forbids), already lowercase, a valid Python
    identifier, and not a Python keyword (a keyword is a valid identifier
    syntactically but cannot bind a dict-attribute-style lookup cleanly).

    Args:
        key: Candidate dict key for the generated ``THEMES`` mapping.

    Returns:
        True if the key satisfies every canonical-key rule.
    """
    return (
        type(key) is str
        and bool(key)
        and key.isascii()
        and key == key.lower()
        and key.isidentifier()
        and not keyword.iskeyword(key)
    )


def canonical_palette(
    colors: list[dict[str, float | int]],
) -> list[dict[str, float | int]]:
    """Return the palette in canonical order (D-24).

    Sorts stably by the stored ``(hue, saturation, brightness, kelvin)``
    tuple, preserving duplicates. The app shuffles palette order on every
    application, so captured order is an accident, not data; sorting a
    multiset preserves it exactly, so unordered palette comparison is
    unaffected. The stored tuple is in ``HSBK``'s user-facing units, not
    protocol uint16.

    That sort order matches ``HSBK.to_protocol()``'s wire order for every
    hue below 359.99725341796875 -- the point where the wire projection
    (``round(0x10000 * hue / 360) % 0x10000``) rounds up to 65536 and wraps
    to wire 0, the same wire colour as hue 0.0. A hue at or above that
    threshold sorts last here even though it would sort first on the wire.
    The schema accepts the full closed 0-360 range, hue 360.0 included, so
    this is a real if narrow divergence, not a theoretical one; nothing in
    this function or its caller guards against it.

    Args:
        colors: Stored user-facing HSBK colour objects.

    Returns:
        A new list sorted by the stored tuple, duplicates preserved.
    """
    return sorted(
        colors,
        key=lambda c: (c["hue"], c["saturation"], c["brightness"], c["kelvin"]),
    )


def _record_label(record: Any) -> str:
    """Best-effort human-readable identifier for a record in error messages."""
    if isinstance(record, dict):
        name = record.get("name")
        if type(name) is str and name:
            return name
        slug = record.get("slug")
        if type(slug) is str and slug:
            return slug
    return "<unidentifiable record>"


def _fail(line_number: int, record: Any, message: str) -> RuntimeError:
    """Build the controlled validation error naming record and JSONL line."""
    return RuntimeError(
        f"themes.jsonl line {line_number}: record '{_record_label(record)}': {message}"
    )


def _validate_colors(line_number: int, record: dict[str, Any]) -> None:
    """Validate a record's ``colors`` field: container, schema, types, ranges."""
    colors = record["colors"]
    if type(colors) is not list:
        raise _fail(line_number, record, "'colors' is not a list")
    if not colors:
        raise _fail(line_number, record, "has zero colours")
    for index, color in enumerate(colors):
        if type(color) is not dict:
            raise _fail(line_number, record, f"colour {index} is not a JSON object")
        missing = _COLOR_FIELDS - color.keys()
        if missing:
            raise _fail(
                line_number,
                record,
                f"colour {index} is missing field(s): {', '.join(sorted(missing))}",
            )
        extra = color.keys() - _COLOR_FIELDS
        if extra:
            raise _fail(
                line_number,
                record,
                f"colour {index} carries unexpected field(s): "
                f"{', '.join(sorted(extra))}",
            )
        for field in sorted(_COLOR_FIELDS):
            value = color[field]
            if field == "kelvin":
                # Kelvin is always a wire integer, never a JSON float.
                # type(v) is int rejects bools (bool is an int subclass, so
                # a range check alone cannot establish integer-ness) and
                # string numerics alike.
                if type(value) is not int:
                    raise _fail(
                        line_number,
                        record,
                        f"colour {index} field '{field}' is not an integer: {value!r}",
                    )
                continue
            # hue, saturation and brightness are user-facing HSBK floats: a
            # JSON number, int or float, but never bool. bool's own type is
            # `bool`, distinct from both `int` and `float`, so this
            # membership test doubles as the bool guard: a range check
            # alone would admit True as 1.0, since bool is an int subclass.
            if type(value) not in (int, float):
                raise _fail(
                    line_number,
                    record,
                    f"colour {index} field '{field}' is not a number: {value!r}",
                )
            # inf passes a naive `<=` range check in one direction and nan
            # fails every comparison silently, so neither is caught by the
            # range test below without checking finiteness first.
            if math.isnan(value) or math.isinf(value):
                raise _fail(
                    line_number,
                    record,
                    f"colour {index} field '{field}' is not a finite number: {value!r}",
                )
        for field, (low, high) in _COLOR_FIELD_RANGES.items():
            value = color[field]
            if not low <= value <= high:
                raise _fail(
                    line_number,
                    record,
                    f"colour {index} field '{field}' out of range {low}-{high}: "
                    f"{value}",
                )
        kelvin = color["kelvin"]
        # Kelvin 0 (KELVIN_SATURATED) is legitimate on an *inbound* read and
        # is never clamped there. Theme data is outbound, blended data:
        # HSBK.average() averages kelvin linearly, so a palette mixing kelvin
        # 0 with any real kelvin lands in the forbidden 1-1499 band and raises
        # inside Canvas.blur(), fill_in_points() and every multizone/matrix
        # apply_theme(). A theme that cannot be rendered must not be
        # generated, so the inbound exemption does not apply here.
        if kelvin == KELVIN_SATURATED:
            raise _fail(
                line_number,
                record,
                f"colour {index} field 'kelvin' is {KELVIN_SATURATED}, which "
                f"is not valid in theme data: {KELVIN_SATURATED} is an "
                f"inbound-only wire value and blending it raises. Re-capture "
                f"the palette with the light in white mode, or drop the colour",
            )
        if not MIN_KELVIN <= kelvin <= MAX_KELVIN:
            raise _fail(
                line_number,
                record,
                f"colour {index} field 'kelvin' out of range "
                f"{MIN_KELVIN}-{MAX_KELVIN}: {kelvin}",
            )


def validate_records(records: list[tuple[int, dict[str, Any]]]) -> None:
    """Validate every record; abort on the first violation.

    Every error is a RuntimeError naming the offending record (display name
    where available) and its JSONL line number. Key collisions name both
    display names involved.

    Args:
        records: ``(line_number, record)`` pairs from ``load_theme_records``.

    Raises:
        RuntimeError: On the first schema, metadata, colour, key or
            collision violation.
    """
    seen_keys: dict[str, str] = {}
    for line_number, record in records:
        if not isinstance(record, dict):
            raise RuntimeError(
                f"themes.jsonl line {line_number}: record is not a JSON object"
            )
        missing = _REQUIRED_FIELDS - record.keys()
        if missing:
            raise _fail(
                line_number,
                record,
                f"missing required field(s): {', '.join(sorted(missing))}",
            )
        extra = record.keys() - _REQUIRED_FIELDS - _OPTIONAL_FIELDS
        if extra:
            raise _fail(
                line_number,
                record,
                f"carries unexpected field(s): {', '.join(sorted(extra))}",
            )
        # name and category are public identity metadata (META-01, META-02):
        # validated here with the same controlled error shape as the colour
        # fields — never an AttributeError or a bare assert.
        for field in ("name", "category"):
            value = record[field]
            if type(value) is not str:
                raise _fail(
                    line_number,
                    record,
                    f"field '{field}' is not a string: {value!r}",
                )
            if not value:
                raise _fail(line_number, record, f"field '{field}' is empty")
            if not value.isascii():
                raise _fail(
                    line_number,
                    record,
                    f"field '{field}' contains non-ASCII characters: {value!r}",
                )
        # disposition is the COMPAT-04 fate of a record: required on every
        # record (D-05), drawn from a closed set.
        disposition = record["disposition"]
        if type(disposition) is not str or disposition not in DISPOSITIONS:
            raise _fail(
                line_number,
                record,
                f"field 'disposition' is {disposition!r}, not one of: "
                f"{', '.join(sorted(DISPOSITIONS))}",
            )
        # A deprecated record must name its successor (D-06); the successor
        # key must be canonical or it could never resolve. Whether the key
        # actually resolves is the cross-record pass after this loop.
        replaced_by = record.get("replaced_by")
        if disposition == "deprecated" and not (
            type(replaced_by) is str and replaced_by
        ):
            raise _fail(
                line_number,
                record,
                f"a deprecated record requires a non-empty 'replaced_by' "
                f"string: {replaced_by!r}",
            )
        # The converse, which theme.py documents as an invariant: only a
        # deprecated record names a successor. Without this, a live record
        # could ship a `replaced_by` and redirect callers away from a theme
        # that was never retired.
        if disposition != "deprecated" and replaced_by is not None:
            raise _fail(
                line_number,
                record,
                f"only a deprecated record may carry 'replaced_by', but "
                f"disposition is {disposition!r} and 'replaced_by' is "
                f"{replaced_by!r}",
            )
        if replaced_by is not None and not validate_key(replaced_by):
            raise _fail(
                line_number,
                record,
                f"replaced_by {replaced_by!r} is not a canonical key "
                f"(non-empty, ASCII, lowercase, valid identifier)",
            )
        _validate_colors(line_number, record)
        aliases = record.get("aliases", [])
        if type(aliases) is not list:
            raise _fail(line_number, record, "'aliases' is not a list")
        for alias in aliases:
            if not validate_key(alias):
                raise _fail(
                    line_number,
                    record,
                    f"alias {alias!r} is not a canonical key (non-empty, "
                    f"ASCII, lowercase, valid identifier)",
                )
        slug = record["slug"]
        if not validate_key(slug):
            raise _fail(
                line_number,
                record,
                f"slug {slug!r} is not a canonical key (non-empty, ASCII, "
                f"lowercase, valid identifier)",
            )
        if slug != derive_slug(record["name"]):
            raise _fail(
                line_number,
                record,
                f"slug {slug!r} does not equal the derivation of its display "
                f"name: expected {derive_slug(record['name'])!r}",
            )
        name = record["name"]
        for key in (slug, *aliases):
            if key in seen_keys:
                raise RuntimeError(
                    f"themes.jsonl line {line_number}: key {key!r} of record "
                    f"'{name}' collides with record '{seen_keys[key]}'"
                )
            seen_keys[key] = name

    # Cross-record pass: every replaced_by must resolve within the data
    # itself. Runs after the main loop so seen_keys holds every slug AND
    # alias — aliases count as resolution targets (SPEC R4: "resolves in
    # THEMES"). Chains onto another deprecated key are permitted by the
    # schema; zero exist today. A chain must still terminate: a record
    # naming itself, or a cycle of records naming each other, resolves in
    # seen_keys yet hangs any consumer that follows replaced_by to find
    # the live successor (`while t.replaced_by: t = get(t.replaced_by)`).
    # Keyed by every resolvable key, not just the slug: a replaced_by may
    # name an alias, and an alias binds the target's own record, so a cycle
    # can be closed through one.
    successors: dict[str, str] = {
        key: record["replaced_by"]
        for _, record in records
        if record.get("replaced_by") is not None
        for key in (record["slug"], *record.get("aliases", []))
    }
    for line_number, record in records:
        replaced_by = record.get("replaced_by")
        if replaced_by is None:
            continue
        if replaced_by not in seen_keys:
            raise _fail(
                line_number,
                record,
                f"replaced_by {replaced_by!r} does not resolve to any slug "
                f"or alias in the data",
            )
        seen_in_chain = {record["slug"], *record.get("aliases", [])}
        cursor: str | None = replaced_by
        while cursor is not None:
            if cursor in seen_in_chain:
                raise _fail(
                    line_number,
                    record,
                    f"replaced_by {replaced_by!r} starts a successor chain "
                    f"that cycles back to {cursor!r} instead of terminating",
                )
            seen_in_chain.add(cursor)
            cursor = successors.get(cursor)
