"""Code generator for the LIFX theme data module.

Reads the committed theme data file (``data/themes.jsonl``) and emits
``src/lifx/theme/data.py``: a frozen ``ThemeRecord`` per theme plus a flat
``THEMES`` dict keyed by slug, plus a synthesised ``disposition="renamed"``
record per rename alias. Regeneration reads only the committed local data
file: no network access and no device are ever required.

The write is atomic: the module is emitted to a uniquely named temp file in
the target directory, formatted there, then renamed over the target. An
interrupted or concurrent run leaves the committed module unchanged and no
stray temp file behind.

This is a repo maintenance script, not library code: it reads a data file
that lives outside the package and is deliberately not shipped in the wheel.

Regenerate with: ``uv run scripts/generate_theme_data.py``
"""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from lifx.color import HSBK
from lifx.theme.schema import (
    DISPOSITIONS,
    RENAMED,
    load_theme_records,
    tag_sort_key,
    validate_key,
    validate_records,
)

#: The repo root: this script lives in ``scripts/`` directly beneath it.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The committed theme data file, in the repo data directory outside the package.
DATA_FILE = REPO_ROOT / "data" / "themes.jsonl"

#: The generated module this generator emits.
OUTPUT_PATH = REPO_ROOT / "src" / "lifx" / "theme" / "data.py"


def _emit_color(color: dict[str, float | int]) -> str:
    """Emit one stored colour as an ``HSBK`` literal.

    Stored values are already in ``HSBK``'s user-facing units, so this is a
    transcription, not a conversion. The ``HSBK`` construction is the guard:
    it applies the library's own component validators, so a value the data
    file's schema admitted but the colour type rejects fails generation
    rather than shipping a module that raises on import.
    """
    hsbk = HSBK(
        hue=color["hue"],
        saturation=color["saturation"],
        brightness=color["brightness"],
        kelvin=cast("int", color["kelvin"]),
    )
    return (
        f"HSBK(hue={hsbk.hue!r}, saturation={hsbk.saturation!r}, "
        f"brightness={hsbk.brightness!r}, kelvin={hsbk.kelvin!r})"
    )


def _emit_literal(name: str, values: list[str]) -> str:
    """Emit a ``Literal`` alias over already-validated identifier values."""
    return f"{name} = Literal[{', '.join(repr(value) for value in values)}]"


def emit_data_module(records: list[tuple[int, dict[str, Any]]]) -> str:
    """Emit the complete source of the generated theme data module.

    Records are emitted sorted by slug. Each record's colours are emitted
    in file order: order is source data (a grid theme's image, a stripe
    theme's sequence), never reordered here. Alias keys are assigned after
    the dict literal in sorted order, each as its own
    ``disposition="renamed"`` record sharing the target's palette object.

    Args:
        records: Validated ``(line_number, record)`` pairs.

    Returns:
        Python source text for ``src/lifx/theme/data.py``.

    Raises:
        RuntimeError: If a defence-in-depth emit-time check fails (a key,
            name or category that escaped validation).
        ValueError: If a colour escaped validation and one of its stored
            fields fails ``HSBK``'s own component validators.
    """
    by_slug = {record["slug"]: record for _, record in records}
    if len(by_slug) != len(records):
        # Keying by slug is last-wins, so a duplicate silently drops a record
        # while its aliases stay in the alias pass below — binding the wrong
        # theme. validate_records() catches this when the documented order is
        # followed; the emit-time backstops exist for when it is not.
        raise RuntimeError("emit-time check failed: duplicate slug in records")
    # The mode value sets are learned from the data, never hard-coded, so a
    # new mode from the app flows through a resync with no hand edit.
    # "blended" is always a static mode (the fallback rendering mode, and it
    # keeps the Literal non-empty); "morph" and "move" are always dynamic
    # modes because Theme.resolved_dynamic_mode can return either.
    # Defence in depth, as for keys below: a mode is interpolated into
    # source, so it must be a canonical identifier. The check runs before
    # the sets are built so a non-string or unhashable mode raises the
    # documented RuntimeError rather than a TypeError from hashing/sorting.
    for _, record in records:
        for field in ("static_mode", "dynamic_mode"):
            if field in record:
                mode = record[field]
                if not (type(mode) is str and validate_key(mode)):
                    raise RuntimeError(f"emit-time check failed: bad mode {mode!r}")
    static_modes = sorted({"blended"} | {r["static_mode"] for _, r in records})
    dynamic_modes = sorted(
        {"morph", "move"}
        | {r["dynamic_mode"] for _, r in records if "dynamic_mode" in r}
    )
    lines: list[str] = [
        '"""Generated LIFX theme data.',
        "",
        "DO NOT EDIT THIS FILE MANUALLY.",
        "Generated from data/themes.jsonl by scripts/generate_theme_data.py",
        "Regenerate with: uv run scripts/generate_theme_data.py",
        "",
        "Colour order is source data, emitted exactly as data/themes.jsonl",
        "gives it. For a grid theme the order is the image and for a stripe",
        "theme it is the stripe sequence, so nothing here reorders it.",
        "",
        "StaticMode and DynamicMode are learned from the data: every mode a",
        "record carries, plus 'blended' (static) and 'morph' and 'move'",
        "(dynamic), which Theme.resolved_dynamic_mode can return.",
        "",
        "Slugs derive from the ASCII display name (D-09): drop apostrophes",
        "and quotation marks, expand '&' to 'and', lowercase, collapse every",
        "run of non-alphanumeric characters to a single underscore, and strip",
        "leading and trailing underscores. unicode_name, when present, is",
        "the accented spelling of the name and folds back to it exactly.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "from typing import Literal",
        "",
        "from lifx.color import HSBK",
        "from lifx.theme.theme import Disposition",
        "",
        _emit_literal("StaticMode", static_modes),
        _emit_literal("DynamicMode", dynamic_modes),
        "",
        "",
        "@dataclass(frozen=True)",
        "class ThemeRecord:",
        '    """A generated theme: identity metadata plus colours in file order."""',
        "",
        "    slug: str",
        "    name: str",
        "    category: str",
        "    disposition: Disposition",
        "    colors: tuple[HSBK, ...]",
        "    static_mode: StaticMode",
        "    dynamic_mode: DynamicMode | None = None",
        "    tags: tuple[str, ...] = ()",
        "    replaced_by: str | None = None",
        "    unicode_name: str | None = None",
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
        # `type(...) is str` before the set membership test, exactly as the
        # metadata backstop above does it: `x in frozenset` raises TypeError
        # for an unhashable x, so an unvalidated list or dict would escape
        # this backstop as a TypeError instead of the documented
        # RuntimeError.
        if type(disposition) is not str or disposition not in DISPOSITIONS:
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
        unicode_name = record.get("unicode_name")
        if unicode_name is not None and not (
            type(unicode_name) is str and unicode_name and not unicode_name.isascii()
        ):
            raise RuntimeError(
                f"emit-time check failed: bad unicode_name {unicode_name!r} "
                f"on record {slug!r}"
            )
        lines.append(f"    {slug!r}: ThemeRecord(")
        lines.append(f"        slug={slug!r},")
        lines.append(f"        name={name!r},")
        if unicode_name is not None:
            lines.append(f"        unicode_name={unicode_name!r},")
        lines.append(f"        category={category!r},")
        lines.append(f"        disposition={disposition!r},")
        lines.append("        colors=(")
        for color in record["colors"]:
            lines.append(f"            {_emit_color(color)},")
        lines.append("        ),")
        lines.append(f"        static_mode={record['static_mode']!r},")
        if "dynamic_mode" in record:
            lines.append(f"        dynamic_mode={record['dynamic_mode']!r},")
        raw_tags = record.get("tags", [])
        if type(raw_tags) is not list:
            raise RuntimeError(
                f"emit-time check failed: bad tags {raw_tags!r} on record {slug!r}"
            )
        for tag in raw_tags:
            if not (
                type(tag) is str
                and tag
                and tag.isascii()
                and tag == tag.strip()
                and tag.isprintable()
            ):
                raise RuntimeError(
                    f"emit-time check failed: bad tag {tag!r} on record {slug!r}"
                )
        # The app's tag order is accidental; a stable order keeps
        # regeneration diffs quiet. tag_sort_key is shared with
        # ThemeLibrary.get_tags().
        tags = tuple(sorted(raw_tags, key=tag_sort_key))
        if tags:
            lines.append(f"        tags={tags!r},")
        # Only deprecated records carry a successor. Emitting
        # `replaced_by=None` on every other record restates the dataclass default
        # and buries the records that do carry one under a field that is
        # noise everywhere else.
        if replaced_by is not None:
            lines.append(f"        replaced_by={replaced_by!r},")
        lines.append("    ),")
    lines.append("}")
    lines.append("")
    aliases = sorted(
        (
            alias,
            record["slug"],
            record["name"],
            record.get("unicode_name"),
            record["category"],
        )
        for _, record in records
        for alias in record.get("aliases", [])
    )
    if aliases:
        lines.append("# Rename aliases: a theme's former key, kept resolvable")
        lines.append("# (D-13, D-14). Each gets its own record rather than")
        lines.append("# binding the target's, so the dead key reports the")
        lines.append("# rename in `disposition` and names the live key in")
        lines.append("# `replaced_by` instead of inheriting the target's clean")
        lines.append("# fate. `slug` is the alias, so following `replaced_by`")
        lines.append("# terminates in one hop; `name` is the target's display")
        lines.append("# name, which is what the theme is actually called now.")
        lines.append("# Modes and tags are shared with the target the same way.")
        for alias, target, name, unicode_name, category in aliases:
            if not validate_key(alias):
                raise RuntimeError(f"emit-time check failed: bad key {alias!r}")
            lines.append(f"THEMES[{alias!r}] = ThemeRecord(")
            lines.append(f"    slug={alias!r},")
            lines.append(f"    name={name!r},")
            if unicode_name is not None:
                lines.append(f"    unicode_name={unicode_name!r},")
            lines.append(f"    category={category!r},")
            lines.append(f"    disposition={RENAMED!r},")
            # The palette is shared, not re-emitted: ThemeRecord is frozen and
            # `colors` is a tuple of immutable HSBK, so one object behind both
            # keys cannot drift and keeps the alias byte-identical by
            # construction rather than by a re-derivation that could differ.
            lines.append(f"    colors=THEMES[{target!r}].colors,")
            lines.append(f"    static_mode=THEMES[{target!r}].static_mode,")
            lines.append(f"    dynamic_mode=THEMES[{target!r}].dynamic_mode,")
            lines.append(f"    tags=THEMES[{target!r}].tags,")
            lines.append(f"    replaced_by={target!r},")
            lines.append(")")
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
