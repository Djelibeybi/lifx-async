"""Code generator for the LIFX theme data module.

Reads the committed theme data file (``data/themes.jsonl``) and emits
``src/lifx/theme/data.py``: a frozen ``ThemeRecord`` per theme plus a flat
``THEMES`` dict keyed by slug, with rename aliases bound to the target's own
record. Regeneration reads only the committed local data file — no network
access and no device are ever required.

The write is atomic: the module is emitted to a uniquely named temp file in
the target directory, formatted there, then renamed over the target. An
interrupted or concurrent run leaves the committed module unchanged and no
stray temp file behind.

This is a repo maintenance script, not library code: it reads a data file
that lives outside the package and is deliberately not shipped in the wheel.

Regenerate with: ``uv run scripts/generate_theme_data.py``
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path
from typing import Any

from lifx.color import HSBK
from lifx.const import KELVIN_SATURATED, MAX_KELVIN, MAX_PALETTE_COLORS, MIN_KELVIN
from lifx.protocol.protocol_types import LightHsbk
from lifx.theme.slug import derive_slug

#: The repo root: this script lives in ``scripts/`` directly beneath it.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The committed theme data file, in the repo data directory outside the package.
DATA_FILE = REPO_ROOT / "data" / "themes.jsonl"

#: The generated module this generator emits.
OUTPUT_PATH = REPO_ROOT / "src" / "lifx" / "theme" / "data.py"

#: Maximum value of a uint16 protocol field (hue, saturation, brightness).
_UINT16_MAX = 0xFFFF

#: Fields every record must carry.
_REQUIRED_FIELDS = frozenset({"slug", "name", "category", "disposition", "colors"})

#: Fields a record may carry in addition to the required set.
_OPTIONAL_FIELDS = frozenset({"aliases", "replaced_by"})

#: Allowed values of a record's ``disposition`` field (COMPAT-04).
_DISPOSITIONS = frozenset({"lifx-app", "library-only", "deprecated"})

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
    deterministic-ASCII rule forbids), already lowercase, and a valid Python
    identifier.

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
    )


def canonical_palette(colors: list[dict[str, int]]) -> list[dict[str, int]]:
    """Return the palette in canonical order (D-24).

    Sorts stably by the stored uint16 ``(hue, saturation, brightness,
    kelvin)`` tuple, preserving duplicates. The app shuffles palette order on
    every application, so captured order is an accident, not data; sorting a
    multiset preserves it exactly, so unordered palette comparison is
    unaffected.

    Args:
        colors: Stored uint16 colour objects.

    Returns:
        A new list sorted by the uint16 tuple, duplicates preserved.
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
    if len(colors) > MAX_PALETTE_COLORS:
        # The firmware effect wire format carries exactly MAX_PALETTE_COLORS
        # slots. A longer palette is silently truncated by the device, so it
        # fails here as a named abort rather than as a ValueError inside
        # MatrixEffect._validate_palette() in user code.
        raise _fail(
            line_number,
            record,
            f"has more than {MAX_PALETTE_COLORS} colours: {len(colors)}",
        )
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
            # type(v) is int rejects bools (bool is an int subclass, so a
            # range check alone cannot establish integer-ness) and string
            # numerics alike.
            if type(value) is not int:
                raise _fail(
                    line_number,
                    record,
                    f"colour {index} field '{field}' is not an integer: {value!r}",
                )
        for field in ("hue", "saturation", "brightness"):
            value = color[field]
            if not 0 <= value <= _UINT16_MAX:
                raise _fail(
                    line_number,
                    record,
                    f"colour {index} field '{field}' out of range 0-65535: {value}",
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
        if type(disposition) is not str or disposition not in _DISPOSITIONS:
            raise _fail(
                line_number,
                record,
                f"field 'disposition' is {disposition!r}, not one of: "
                f"{', '.join(sorted(_DISPOSITIONS))}",
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
    # schema; zero exist today.
    for line_number, record in records:
        replaced_by = record.get("replaced_by")
        if replaced_by is not None and replaced_by not in seen_keys:
            raise _fail(
                line_number,
                record,
                f"replaced_by {replaced_by!r} does not resolve to any slug "
                f"or alias in the data",
            )


def _emit_color(color: dict[str, int]) -> str:
    """Emit one stored uint16 colour as a full-precision HSBK literal.

    Converts the stored uint16 values to user-facing floats via the
    protocol path, then guards the round-trip: the emitted literal's
    ``as_tuple()`` must equal the stored uint16 tuple exactly.

    Args:
        color: Stored uint16 colour object.

    Returns:
        Source text for one ``HSBK(...)`` constructor call.

    Raises:
        RuntimeError: If the emitted value does not round-trip to the
            stored uint16 tuple.
    """
    stored = (
        color["hue"],
        color["saturation"],
        color["brightness"],
        color["kelvin"],
    )
    hsbk = HSBK.from_protocol(
        LightHsbk(
            hue=color["hue"],
            saturation=color["saturation"],
            brightness=color["brightness"],
            kelvin=color["kelvin"],
        )
    )
    if hsbk.as_tuple() != stored:
        raise RuntimeError(
            f"round-trip mismatch: stored uint16 {stored} re-encodes as "
            f"{hsbk.as_tuple()}"
        )
    return (
        f"HSBK(hue={hsbk.hue!r}, saturation={hsbk.saturation!r}, "
        f"brightness={hsbk.brightness!r}, kelvin={hsbk.kelvin!r})"
    )


def emit_data_module(records: list[tuple[int, dict[str, Any]]]) -> str:
    """Emit the complete source of the generated theme data module.

    Records are emitted sorted by slug; each palette passes through
    ``canonical_palette()`` (D-24) so even a hand-edited data file cannot
    ship an uncanonical order. Alias keys are assigned after the dict
    literal in sorted order, binding the target's own record so the alias
    carries the target's identity.

    Args:
        records: Validated ``(line_number, record)`` pairs.

    Returns:
        Python source text for ``src/lifx/theme/data.py``.

    Raises:
        RuntimeError: If a defence-in-depth emit-time check fails (a key,
            name or category that escaped validation, or a colour that does
            not round-trip at uint16).
    """
    by_slug = {record["slug"]: record for _, record in records}
    if len(by_slug) != len(records):
        # Keying by slug is last-wins, so a duplicate silently drops a record
        # while its aliases stay in the alias pass below — binding the wrong
        # theme. validate_records() catches this when the documented order is
        # followed; the emit-time backstops exist for when it is not.
        raise RuntimeError("emit-time check failed: duplicate slug in records")
    lines: list[str] = [
        '"""Generated LIFX theme data.',
        "",
        "DO NOT EDIT THIS FILE MANUALLY.",
        "Generated from data/themes.jsonl by scripts/generate_theme_data.py",
        "Regenerate with: uv run scripts/generate_theme_data.py",
        "",
        "Palette order is canonical, not captured: every palette is sorted by",
        "its normalised (hue, saturation, brightness, kelvin) uint16 tuple,",
        "duplicates preserved (D-24). The LIFX app shuffles palette order on",
        "every application, so captured order is an accident, not data.",
        "",
        "Slugs derive from the emoji-stripped display name: NFKD-normalise,",
        "drop non-ASCII, lowercase, collapse every run of non-alphanumeric",
        "characters to a single underscore, strip leading and trailing",
        "underscores (D-09).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "from lifx.color import HSBK",
        "",
        "",
        "@dataclass(frozen=True)",
        "class ThemeRecord:",
        '    """A generated theme: identity metadata plus canonical palette."""',
        "",
        "    slug: str",
        "    name: str",
        "    category: str",
        "    disposition: str",
        "    colors: tuple[HSBK, ...]",
        "    replaced_by: str | None = None",
        "",
        "",
        "THEMES: dict[str, ThemeRecord] = {",
    ]
    for slug in sorted(by_slug):
        record = by_slug[slug]
        name = record["name"]
        category = record["category"]
        # Defence in depth: the primary, controlled checks live in
        # validate_records(); these backstops re-assert the invariants a
        # hostile record would need to break to inject source text.
        if not validate_key(slug):
            raise RuntimeError(f"emit-time check failed: bad key {slug!r}")
        for value in (name, category):
            if not (type(value) is str and value and value.isascii()):
                raise RuntimeError(
                    f"emit-time check failed: bad metadata {value!r} on record {slug!r}"
                )
        disposition = record["disposition"]
        if disposition not in _DISPOSITIONS:
            raise RuntimeError(
                f"emit-time check failed: bad disposition {disposition!r} "
                f"on record {slug!r}"
            )
        replaced_by = record.get("replaced_by")
        if replaced_by is not None and not validate_key(replaced_by):
            raise RuntimeError(
                f"emit-time check failed: bad replaced_by {replaced_by!r} "
                f"on record {slug!r}"
            )
        lines.append(f"    {slug!r}: ThemeRecord(")
        lines.append(f"        slug={slug!r},")
        lines.append(f"        name={name!r},")
        lines.append(f"        category={category!r},")
        lines.append(f"        disposition={disposition!r},")
        lines.append("        colors=(")
        for color in canonical_palette(record["colors"]):
            lines.append(f"            {_emit_color(color)},")
        lines.append("        ),")
        lines.append(f"        replaced_by={replaced_by!r},")
        lines.append("    ),")
    lines.append("}")
    lines.append("")
    aliases = sorted(
        (alias, record["slug"])
        for _, record in records
        for alias in record.get("aliases", [])
    )
    if aliases:
        lines.append("# Rename aliases: each alias key binds the target's own")
        lines.append("# record, so the alias carries the target's identity")
        lines.append("# (D-13, D-14).")
        for alias, target in aliases:
            if not validate_key(alias):
                raise RuntimeError(f"emit-time check failed: bad key {alias!r}")
            lines.append(f"THEMES[{alias!r}] = THEMES[{target!r}]")
        lines.append("")
    return "\n".join(lines)


def format_generated_files(*paths: Path) -> None:
    """Run `ruff format` and `ruff check --fix` over the generated files.

    The generator emits valid but unformatted Python: string quoting and line
    wrapping differ from the repository style, so an unformatted regeneration
    shows up as a large spurious diff.

    Args:
        paths: Files to format in place.

    Raises:
        RuntimeError: If ruff cannot format or lint the generated files.
    """
    print("Formatting generated code with ruff...")
    targets = [str(path) for path in paths]

    for command in (["format"], ["check", "--fix"]):
        result = subprocess.run(  # nosec B603
            [sys.executable, "-m", "ruff", *command, *targets],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # ruff writes diagnostics to stdout and internal errors to stderr,
            # so both are needed to explain the failure. `ruff format` only
            # fails on unparsable Python, which means the generator emitted
            # broken code: never let that pass as a successful generation.
            diagnostics = "\n".join(
                stream.strip()
                for stream in (result.stdout, result.stderr)
                if stream.strip()
            )
            raise RuntimeError(
                f"ruff {command[0]} failed on the generated files:\n{diagnostics}"
            )


def main() -> None:
    """Load, validate, emit and atomically write the theme data module.

    The module is written to a uniquely named temp file in the target
    directory (so the final ``Path.replace()`` is a same-filesystem atomic
    rename and two concurrent runs cannot race on a shared temp path),
    formatted there, then renamed over the target. The temp file is removed
    unconditionally on every failure path, so an interrupted run leaves the
    committed module unchanged and no stray file behind.
    """
    records = load_theme_records(DATA_FILE)
    validate_records(records)
    source = emit_data_module(records)

    handle, temp_name = tempfile.mkstemp(dir=OUTPUT_PATH.parent, suffix=".py")
    temp_path = Path(temp_name)
    try:
        # Close the mkstemp handle before ruff touches the file.
        os.close(handle)
        temp_path.write_text(source, encoding="utf-8")
        format_generated_files(temp_path)
        # mkstemp creates the file 0600 and Path.replace() carries that mode
        # onto the target, so widen it to the mode every other tracked source
        # file in this repo already has. Fixed rather than umask-derived: git
        # tracks only the exec bit, so a maintainer running under `umask 077`
        # would otherwise narrow data.py to 0600 invisibly and ship an
        # owner-only module inside the wheel.
        temp_path.chmod(0o644)
        temp_path.replace(OUTPUT_PATH)
    finally:
        # A no-op after a successful rename; removes the temp file when
        # validation, writing or ruff raised part-way.
        temp_path.unlink(missing_ok=True)

    print(f"Generated {OUTPUT_PATH} ({len(records)} records)")


if __name__ == "__main__":
    main()
