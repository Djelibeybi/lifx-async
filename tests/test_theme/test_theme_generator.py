"""Comprehensive tests for the LIFX theme data module generator.

Tests cover:
- JSONL loading and malformed-line aborts with line numbers
- Canonical-key validation for primary slugs AND aliases
- D-09 slug derivation from stored display names
- Record schema validation aborts (missing/extra fields, wrong containers,
  string numerics, booleans) naming the record and its JSONL line number
- Name/category metadata validation (non-string, empty, non-ASCII)
- Key collision aborts naming both display names
- Colour range validation (kelvin 0 is inbound-only and rejected here) and
  the 16-slot wire palette ceiling
- Canonical palette ordering (D-24) with duplicates preserved
- Alias expansion binding the target's own record (D-13, D-14)
- uint16 round-trip exactness of emitted HSBK literals
- Deterministic emission
- Atomic write via a uniquely named temp file (D-05)

All tests run against fixture data in tmp_path — never against the committed
data/themes.jsonl (D-23: the data file is the record of what should exist; no
drift check, no count assertions against real data).
"""

from __future__ import annotations

import ast
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import generate_theme_data as generator_module
import pytest
from generate_theme_data import (
    canonical_palette,
    derive_slug,
    emit_data_module,
    load_theme_records,
    main,
    validate_key,
    validate_records,
)

import lifx.theme.slug
from lifx.const import MAX_PALETTE_COLORS

# ============================================================================
# Fixture helpers
# ============================================================================


def _color(
    hue: int = 0,
    saturation: int = 65535,
    brightness: int = 65535,
    kelvin: int = 3500,
) -> dict[str, Any]:
    """Build one stored uint16 colour object."""
    return {
        "hue": hue,
        "saturation": saturation,
        "brightness": brightness,
        "kelvin": kelvin,
    }


def _record(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid record, then apply overrides."""
    record: dict[str, Any] = {
        "slug": "test_theme",
        "name": "Test Theme",
        "category": "Test",
        "disposition": "lifx-app",
        "colors": [_color()],
    }
    record.update(overrides)
    return record


def _pairs(*records: Any) -> list[tuple[int, dict[str, Any]]]:
    """Attach one-based line numbers to records, as load_theme_records does."""
    return list(enumerate(records, start=1))


def _exec_module(source: str) -> dict[str, Any]:
    """Execute emitted module source and return its namespace."""
    namespace: dict[str, Any] = {}
    exec(compile(source, "<generated>", "exec"), namespace)
    return namespace


# ============================================================================
# Tests for load_theme_records()
# ============================================================================


class TestLoadThemeRecords:
    """Tests for JSONL parsing with line-number tracking."""

    def test_returns_line_number_record_pairs(self, tmp_path: Path) -> None:
        """Each record travels with its one-based line number."""
        data_file = tmp_path / "themes.jsonl"
        data_file.write_text(
            json.dumps(_record()) + "\n" + json.dumps(_record(slug="other")) + "\n"
        )

        pairs = load_theme_records(data_file)

        assert [line for line, _ in pairs] == [1, 2]
        assert pairs[0][1]["slug"] == "test_theme"
        assert pairs[1][1]["slug"] == "other"

    def test_blank_lines_skipped_line_numbers_preserved(self, tmp_path: Path) -> None:
        """Blank lines are skipped but do not shift later line numbers."""
        data_file = tmp_path / "themes.jsonl"
        data_file.write_text(json.dumps(_record()) + "\n\n" + json.dumps(_record()))

        pairs = load_theme_records(data_file)

        assert [line for line, _ in pairs] == [1, 3]

    def test_malformed_line_aborts_naming_line_number(self, tmp_path: Path) -> None:
        """A non-JSON line aborts with a RuntimeError naming the line."""
        data_file = tmp_path / "themes.jsonl"
        data_file.write_text(json.dumps(_record()) + "\nnot json\n")

        with pytest.raises(RuntimeError, match=r"line 2.*not valid JSON"):
            load_theme_records(data_file)


# ============================================================================
# Tests for validate_key()
# ============================================================================


class TestValidateKey:
    """Tests for the canonical-key predicate (slugs AND aliases)."""

    @pytest.mark.parametrize("key", ["forest", "test_theme", "a", "colour_1"])
    def test_valid_keys(self, key: str) -> None:
        """Canonical keys pass: non-empty, ASCII, lowercase, identifier."""
        assert validate_key(key) is True

    @pytest.mark.parametrize(
        "key",
        [
            "",
            "bad-alias",
            "1bad",
            "café",
            "Forest",
            "with space",
            42,
            None,
            ["forest"],
        ],
    )
    def test_invalid_keys(self, key: Any) -> None:
        """Empty, hyphenated, digit-leading, Unicode, uppercase and
        non-string keys all fail."""
        assert validate_key(key) is False


# ============================================================================
# Tests for derive_slug()
# ============================================================================


class TestDeriveSlug:
    """Tests for the D-09 slug derivation over stored ASCII names."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Test Theme", "test_theme"),
            ("Forrest", "forrest"),
            ("Valentine's", "valentine_s"),
            ("Dance/Pop", "dance_pop"),
            ("  Padded  ", "padded"),
            ("Multi - Punct!", "multi_punct"),
        ],
    )
    def test_derivation(self, name: str, expected: str) -> None:
        """Lowercase, collapse non-alphanumeric runs to one underscore,
        strip leading/trailing underscores."""
        assert derive_slug(name) == expected

    def test_generator_shares_the_package_rule(self) -> None:
        """The generator's derive_slug IS the package's (identity, D-04).

        A second copy anywhere would reintroduce the drift D-04 forbids;
        identity — not equality — proves there is exactly one implementation.
        """
        assert generator_module.derive_slug is lifx.theme.slug.derive_slug


# ============================================================================
# Tests for canonical_palette()
# ============================================================================


class TestCanonicalPalette:
    """Tests for D-24 canonical palette ordering."""

    def test_sorts_by_uint16_tuple(self) -> None:
        """Palettes sort by (hue, saturation, brightness, kelvin)."""
        c1 = _color(hue=100)
        c2 = _color(hue=200)
        c3 = _color(hue=300)

        assert canonical_palette([c3, c1, c2]) == [c1, c2, c3]

    def test_duplicates_preserved(self) -> None:
        """Sorting a multiset preserves it — duplicates survive."""
        c1 = _color(hue=100)
        c2 = _color(hue=200)

        result = canonical_palette([c2, c1, c2])

        assert result == [c1, c2, c2]
        assert len(result) == 3

    def test_input_not_mutated(self) -> None:
        """The original list is left untouched."""
        original = [_color(hue=300), _color(hue=100)]
        snapshot = list(original)

        canonical_palette(original)

        assert original == snapshot


# ============================================================================
# Tests for validate_records() — abort cases
# ============================================================================


class TestValidateRecordsKeys:
    """Slug and alias canonical-key aborts."""

    def test_empty_slug_aborts_naming_display_name(self) -> None:
        """An empty slug aborts naming the offending display name."""
        with pytest.raises(RuntimeError, match=r"Test Theme.*not a canonical key"):
            validate_records(_pairs(_record(slug="")))

    def test_non_identifier_slug_aborts(self) -> None:
        """A slug failing str.isidentifier() aborts naming the display name."""
        with pytest.raises(RuntimeError, match=r"Test Theme.*'bad-slug'"):
            validate_records(_pairs(_record(slug="bad-slug")))

    def test_digit_leading_slug_aborts(self) -> None:
        """A digit-leading slug aborts (identifier rule, no relaxation)."""
        with pytest.raises(RuntimeError, match=r"'1bad'.*not a canonical key"):
            validate_records(_pairs(_record(slug="1bad", name="1bad")))

    def test_unicode_identifier_slug_aborts(self) -> None:
        """A slug passing isidentifier() but failing isascii() aborts —
        the canonical-key check closes the Unicode-identifier loophole."""
        assert "café".isidentifier()
        with pytest.raises(RuntimeError, match=r"not a canonical key"):
            validate_records(_pairs(_record(slug="café")))

    @pytest.mark.parametrize("alias", ["bad-alias", "", "café"])
    def test_invalid_alias_aborts_naming_record(self, alias: str) -> None:
        """A hyphenated, empty or Unicode alias aborts naming the carrying
        record — aliases pass the same canonical-key check as slugs."""
        with pytest.raises(RuntimeError, match=r"Test Theme.*alias"):
            validate_records(_pairs(_record(aliases=[alias])))

    def test_slug_not_matching_derivation_aborts(self) -> None:
        """A primary slug that does not equal derive_slug(name) aborts."""
        with pytest.raises(
            RuntimeError, match=r"Test Theme.*does not equal the derivation"
        ):
            validate_records(_pairs(_record(slug="wrong_slug")))


class TestValidateRecordsSchema:
    """Record schema aborts naming record AND JSONL line number."""

    def test_record_not_an_object_aborts(self) -> None:
        """A non-object record aborts naming the line."""
        with pytest.raises(RuntimeError, match=r"line 1.*not a JSON object"):
            validate_records(_pairs(["not", "a", "record"]))

    def test_missing_required_field_aborts(self) -> None:
        """A record missing a required field aborts naming record and line."""
        record = _record()
        del record["category"]

        with pytest.raises(
            RuntimeError, match=r"line 1.*Test Theme.*missing required field.*category"
        ):
            validate_records(_pairs(record))

    def test_unexpected_field_aborts(self) -> None:
        """A record carrying an unexpected field aborts."""
        with pytest.raises(
            RuntimeError, match=r"line 1.*Test Theme.*unexpected field.*index"
        ):
            validate_records(_pairs(_record(index=3)))

    def test_colors_not_a_list_aborts(self) -> None:
        """A colors field that is not a list aborts."""
        with pytest.raises(RuntimeError, match=r"line 1.*'colors' is not a list"):
            validate_records(_pairs(_record(colors={"hue": 0})))

    def test_colour_entry_not_an_object_aborts(self) -> None:
        """A colour that is not a JSON object aborts naming its index."""
        with pytest.raises(
            RuntimeError, match=r"line 1.*colour 0 is not a JSON object"
        ):
            validate_records(_pairs(_record(colors=["not a colour"])))

    def test_non_dict_record_labelled_generically(self) -> None:
        """A non-dict reaching the error builder is labelled, not crashed.

        validate_records() rejects non-objects before ever calling _fail(),
        so this arc is defensive only — but _fail() is the single error
        constructor and must never raise an error of its own.
        """
        error = generator_module._fail(7, ["not", "a", "record"], "bad thing")

        assert "unidentifiable record" in str(error)
        assert "line 7" in str(error)

    def test_unidentifiable_record_named_generically(self) -> None:
        """A record carrying neither name nor slug still aborts cleanly.

        ``_record_label()`` has nothing to quote, so the error names the
        record generically rather than raising a KeyError of its own.
        """
        with pytest.raises(
            RuntimeError, match=r"line 1.*unidentifiable record.*missing required field"
        ):
            validate_records(_pairs({"category": "Test", "colors": [_color()]}))

    def test_aliases_not_a_list_aborts(self) -> None:
        """An aliases field that is not a list aborts."""
        with pytest.raises(RuntimeError, match=r"line 1.*'aliases' is not a list"):
            validate_records(_pairs(_record(aliases="forest")))

    def test_color_missing_field_aborts(self) -> None:
        """A colour object missing a field aborts naming record and line."""
        color = _color()
        del color["kelvin"]

        with pytest.raises(
            RuntimeError, match=r"line 1.*Test Theme.*colour 0.*missing.*kelvin"
        ):
            validate_records(_pairs(_record(colors=[color])))

    def test_color_extra_field_aborts(self) -> None:
        """A colour object carrying an extra field aborts."""
        color = _color()
        color["alpha"] = 1

        with pytest.raises(
            RuntimeError, match=r"line 1.*colour 0.*unexpected field.*alpha"
        ):
            validate_records(_pairs(_record(colors=[color])))

    def test_string_numeric_color_value_aborts(self) -> None:
        """A string numeric colour value aborts — not an integer."""
        with pytest.raises(
            RuntimeError, match=r"line 1.*'hue' is not an integer: '100'"
        ):
            validate_records(_pairs(_record(colors=[_color(hue="100")])))

    def test_bool_color_value_aborts(self) -> None:
        """A boolean colour value aborts even though True passes an integer
        range check — bool is an int in Python, so type(v) is int is the
        only discriminating test of integer-ness."""
        with pytest.raises(
            RuntimeError, match=r"line 1.*'saturation' is not an integer: True"
        ):
            validate_records(_pairs(_record(colors=[_color(saturation=True)])))

    def test_line_number_reflects_position(self) -> None:
        """The reported line number is the failing record's own line."""
        bad = _record(slug="second_theme", name="Second Theme", colors=[])

        with pytest.raises(RuntimeError, match=r"line 2.*Second Theme"):
            validate_records(_pairs(_record(), bad))


class TestValidateRecordsMetadata:
    """Name/category metadata aborts (META-01, META-02, D-06)."""

    @pytest.mark.parametrize("field", ["name", "category"])
    @pytest.mark.parametrize(
        ("value", "fragment"),
        [
            (42, "is not a string"),
            ("", "is empty"),
            ("Café", "contains non-ASCII"),
        ],
    )
    def test_invalid_metadata_aborts(
        self, field: str, value: Any, fragment: str
    ) -> None:
        """A non-string, empty or non-ASCII name/category aborts with the
        same controlled RuntimeError shape as the colour-field checks —
        never an AttributeError or a bare AssertionError."""
        with pytest.raises(RuntimeError, match=rf"line 1.*'{field}' {fragment}"):
            validate_records(_pairs(_record(**{field: value})))


class TestValidateRecordsCollisions:
    """Key collision aborts naming BOTH display names."""

    def test_duplicate_slug_aborts_naming_both_names(self) -> None:
        """Two records resolving to the same slug abort naming both."""
        first = _record(slug="same_theme", name="Same Theme")
        second = _record(slug="same_theme", name="Same-Theme")

        with pytest.raises(RuntimeError) as exc_info:
            validate_records(_pairs(first, second))

        message = str(exc_info.value)
        assert "Same Theme" in message
        assert "Same-Theme" in message

    def test_alias_colliding_with_slug_aborts_naming_both(self) -> None:
        """An alias colliding with an existing slug aborts naming both."""
        first = _record(slug="alpha_theme", name="Alpha Theme")
        second = _record(slug="beta_theme", name="Beta Theme", aliases=["alpha_theme"])

        with pytest.raises(RuntimeError) as exc_info:
            validate_records(_pairs(first, second))

        message = str(exc_info.value)
        assert "Alpha Theme" in message
        assert "Beta Theme" in message


class TestValidateRecordsDispositions:
    """The three D-08 disposition validations (COMPAT-04) and their branches."""

    def test_unknown_disposition_aborts(self) -> None:
        """An unknown disposition aborts naming record, line and value."""
        with pytest.raises(
            RuntimeError,
            match=r"line 1.*Test Theme.*'disposition' is 'retired', not one of",
        ):
            validate_records(_pairs(_record(disposition="retired")))

    def test_deprecated_without_replacement_aborts(self) -> None:
        """A deprecated record with no replaced_by aborts with the
        controlled deprecated-requires-replaced_by error (SPEC R4)."""
        with pytest.raises(
            RuntimeError,
            match=r"line 1.*Test Theme.*deprecated record requires a "
            r"non-empty 'replaced_by'",
        ):
            validate_records(_pairs(_record(disposition="deprecated")))

    def test_unresolvable_replaced_by_aborts(self) -> None:
        """A canonical replaced_by absent from every slug and alias aborts
        in the cross-record pass, naming the unresolvable key."""
        with pytest.raises(
            RuntimeError,
            match=r"line 1.*Test Theme.*replaced_by 'no_such_theme' does "
            r"not resolve",
        ):
            validate_records(
                _pairs(_record(disposition="deprecated", replaced_by="no_such_theme"))
            )

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            # The type-check side of the disposition condition, distinct
            # from the unknown-string side above.
            ({"disposition": 123}, r"'disposition' is 123, not one of"),
            # The falsy side of the replaced_by presence condition.
            (
                {"disposition": "deprecated", "replaced_by": ""},
                r"deprecated record requires a non-empty 'replaced_by' string: ''",
            ),
            # The type-check side of the replaced_by presence condition.
            (
                {"disposition": "deprecated", "replaced_by": 123},
                r"deprecated record requires a non-empty 'replaced_by' string: 123",
            ),
            # Present but non-canonical: a different branch from the
            # unresolved-but-canonical case above.
            (
                {"disposition": "deprecated", "replaced_by": "Bad-Key"},
                r"replaced_by 'Bad-Key' is not a canonical key",
            ),
        ],
    )
    def test_bad_value_branches_abort(
        self, overrides: dict[str, Any], expected: str
    ) -> None:
        """Every bad-value side of the compound disposition conditions
        aborts with its own controlled message (review F1)."""
        with pytest.raises(RuntimeError, match=expected):
            validate_records(_pairs(_record(**overrides)))

    def test_replaced_by_resolving_via_alias_validates(self) -> None:
        """A replaced_by naming an alias of another record validates —
        aliases count as resolution targets (SPEC R4: resolves in THEMES)."""
        target = _record(slug="new_theme", name="New Theme", aliases=["old_alias"])
        deprecated = _record(
            slug="old_theme",
            name="Old Theme",
            disposition="deprecated",
            replaced_by="old_alias",
        )

        validate_records(_pairs(target, deprecated))


class TestValidateRecordsColors:
    """Colour count and range aborts."""

    def test_zero_colors_aborts_naming_display_name(self) -> None:
        """A record with zero colours aborts naming the display name."""
        with pytest.raises(RuntimeError, match=r"Test Theme.*zero colours"):
            validate_records(_pairs(_record(colors=[])))

    @pytest.mark.parametrize(
        "color",
        [
            _color(hue=65536),
            _color(saturation=-1),
            _color(brightness=70000),
            _color(kelvin=1000),
            _color(kelvin=9001),
        ],
    )
    def test_out_of_range_color_aborts(self, color: dict[str, Any]) -> None:
        """An out-of-range colour field aborts naming record and line."""
        with pytest.raises(RuntimeError, match=r"line 1.*out of range"):
            validate_records(_pairs(_record(colors=[color])))

    def test_kelvin_zero_aborts_on_outbound_theme_data(self) -> None:
        """Kelvin 0 is inbound-only; a theme is outbound, blended data.

        ``HSBK.average()`` averages kelvin linearly, so a palette mixing
        kelvin 0 with any real kelvin lands in the forbidden 1-1499 band and
        raises inside every multizone/matrix ``apply_theme()`` path.
        """
        with pytest.raises(RuntimeError, match=r"line 1.*kelvin.*not valid in theme"):
            validate_records(_pairs(_record(colors=[_color(kelvin=0)])))

    def test_palette_over_wire_ceiling_aborts(self) -> None:
        """A palette above the 16-slot wire ceiling aborts at generation."""
        colors = [_color(hue=index) for index in range(MAX_PALETTE_COLORS + 1)]
        with pytest.raises(RuntimeError, match=r"line 1.*more than 16 colours"):
            validate_records(_pairs(_record(colors=colors)))

    def test_palette_at_wire_ceiling_is_accepted(self) -> None:
        """Exactly 16 colours is the ceiling, not one past it."""
        colors = [_color(hue=index) for index in range(MAX_PALETTE_COLORS)]
        validate_records(_pairs(_record(colors=colors)))


# ============================================================================
# Tests for emit_data_module()
# ============================================================================


class TestEmitDataModule:
    """Tests for the emitted module source."""

    def test_module_docstring_names_source_and_generator(self) -> None:
        """The emitted module starts with a do-not-edit docstring naming
        both the data file and the generator."""
        source = emit_data_module(_pairs(_record()))

        assert source.startswith('"""')
        docstring = ast.get_docstring(ast.parse(source))
        assert docstring is not None
        assert "DO NOT EDIT" in docstring
        assert "themes.jsonl" in docstring
        assert "scripts/generate_theme_data.py" in docstring

    def test_alias_binds_target_record(self) -> None:
        """The alias key binds the target's own record, so both keys share
        one record carrying the target's slug/name/category (D-13, D-14)."""
        record = _record(slug="alpha_theme", name="Alpha Theme", aliases=["old_alpha"])

        namespace = _exec_module(emit_data_module(_pairs(record)))

        themes = namespace["THEMES"]
        assert themes["old_alpha"] is themes["alpha_theme"]
        assert themes["old_alpha"].slug == "alpha_theme"
        assert themes["old_alpha"].name == "Alpha Theme"
        assert themes["old_alpha"].category == "Test"

    def test_palette_emitted_canonically_sorted(self) -> None:
        """A record whose colours arrive unsorted is emitted sorted by its
        uint16 tuple, with a duplicated colour surviving in both positions
        (D-24)."""
        c1 = _color(hue=100)
        c2 = _color(hue=200)
        c3 = _color(hue=300)
        record = _record(colors=[c3, c1, c2, c1])

        namespace = _exec_module(emit_data_module(_pairs(record)))

        emitted = [c.as_tuple() for c in namespace["THEMES"]["test_theme"].colors]
        assert emitted == sorted(emitted)
        assert len(emitted) == 4
        assert emitted.count((100, 65535, 65535, 3500)) == 2

    @pytest.mark.parametrize(
        "color",
        [
            _color(hue=0, saturation=0, brightness=0, kelvin=3500),
            _color(hue=65535, saturation=65535, brightness=65535, kelvin=9000),
            _color(hue=32768, saturation=12345, brightness=54321, kelvin=1500),
        ],
    )
    def test_uint16_round_trip_exact(self, color: dict[str, Any]) -> None:
        """The emitted HSBK literal's as_tuple() equals the stored uint16
        tuple for boundary and mid values."""
        stored = (
            color["hue"],
            color["saturation"],
            color["brightness"],
            color["kelvin"],
        )

        namespace = _exec_module(emit_data_module(_pairs(_record(colors=[color]))))

        (emitted,) = namespace["THEMES"]["test_theme"].colors
        assert emitted.as_tuple() == stored

    def test_duplicate_colors_survive_as_multiset(self) -> None:
        """Duplicate colours in a record survive into the emitted module
        exactly — multiset, never a set."""
        c1 = _color(hue=100)
        record = _record(colors=[c1, c1, _color(hue=200)])

        namespace = _exec_module(emit_data_module(_pairs(record)))

        counts = Counter(c.as_tuple() for c in namespace["THEMES"]["test_theme"].colors)
        assert counts[(100, 65535, 65535, 3500)] == 2
        assert counts[(200, 65535, 65535, 3500)] == 1

    @pytest.mark.parametrize(
        ("record", "expected"),
        [
            (_record(slug="bad-slug", name="Bad Slug"), r"bad key 'bad-slug'"),
            (_record(name="Café"), r"bad metadata 'Café'"),
            (_record(category=""), r"bad metadata ''"),
            (
                _record(aliases=["bad-alias"]),
                r"bad key 'bad-alias'",
            ),
            (_record(disposition="retired"), r"bad disposition 'retired'"),
            (
                _record(replaced_by="Bad-Key"),
                r"bad replaced_by 'Bad-Key'",
            ),
        ],
    )
    def test_emit_time_backstops_reject_unvalidated_records(
        self, record: dict[str, Any], expected: str
    ) -> None:
        """Emit-time checks hold when validate_records() was not run first.

        emit_data_module() is public and directly callable, so its backstops
        must re-assert every invariant a hostile record would need to break
        to inject source text into the generated module.
        """
        with pytest.raises(RuntimeError, match=expected):
            emit_data_module(_pairs(record))

    def test_round_trip_mismatch_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A colour that does not re-encode to its stored uint16 aborts.

        Unreachable through the protocol path today; the check exists so a
        future HSBK conversion change cannot silently ship drifted palettes.
        """
        monkeypatch.setattr(
            generator_module.HSBK,
            "as_tuple",
            lambda self: (1, 2, 3, 4),
        )

        with pytest.raises(RuntimeError, match="round-trip mismatch"):
            emit_data_module(_pairs(_record()))

    def test_duplicate_slug_aborts_at_emit_time(self) -> None:
        """Two records sharing a slug abort rather than last-wins.

        Keying by slug is last-wins, so the first record would vanish while
        its aliases stayed bound — to the *wrong* theme. validate_records()
        catches this when the documented order is followed; this backstop
        holds when emit_data_module() is called directly.
        """
        records = _pairs(
            _record(slug="alpha", name="Alpha", aliases=["old_alpha"]),
            _record(slug="alpha", name="Alpha"),
        )

        with pytest.raises(RuntimeError, match="duplicate slug"):
            emit_data_module(records)

    def test_disposition_round_trips_through_emitted_module(self) -> None:
        """disposition and replaced_by survive emit into the executed
        THEMES: the deprecated record carries its successor key and the
        lifx-app record's replaced_by prints as None."""
        deprecated = _record(
            slug="old_theme",
            name="Old Theme",
            disposition="deprecated",
            replaced_by="new_theme",
        )
        replacement = _record(slug="new_theme", name="New Theme")

        namespace = _exec_module(emit_data_module(_pairs(deprecated, replacement)))

        themes = namespace["THEMES"]
        assert themes["old_theme"].disposition == "deprecated"
        assert themes["old_theme"].replaced_by == "new_theme"
        assert themes["new_theme"].disposition == "lifx-app"
        assert themes["new_theme"].replaced_by is None

    def test_deterministic_output(self) -> None:
        """emit_data_module() called twice over the same records returns
        identical strings."""
        records = _pairs(
            _record(slug="alpha_theme", name="Alpha Theme", aliases=["old_alpha"]),
            _record(slug="beta_theme", name="Beta Theme"),
        )

        assert emit_data_module(records) == emit_data_module(records)


# ============================================================================
# Tests for format_generated_files()
# ============================================================================


class TestFormatGeneratedFiles:
    """The ruff invocation and its failure reporting."""

    def test_ruff_failure_raises_with_both_streams(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A non-zero ruff exit aborts, quoting stdout and stderr.

        ``ruff format`` only fails on unparsable Python, which means the
        generator emitted broken code — that must never pass as a successful
        generation, and the diagnostics are needed to explain why.
        """

        class _Result:
            returncode = 1
            stdout = "error: unparsable input\n"
            stderr = "ruff internal failure\n"

        monkeypatch.setattr(
            generator_module.subprocess, "run", lambda *a, **k: _Result()
        )

        with pytest.raises(RuntimeError) as exc_info:
            generator_module.format_generated_files(tmp_path / "data.py")

        message = str(exc_info.value)
        assert "ruff format failed" in message
        assert "unparsable input" in message
        assert "ruff internal failure" in message

    def test_ruff_failure_with_empty_streams_still_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A silent non-zero exit still aborts, with empty diagnostics."""

        class _Result:
            returncode = 2
            stdout = ""
            stderr = "   "

        monkeypatch.setattr(
            generator_module.subprocess, "run", lambda *a, **k: _Result()
        )

        with pytest.raises(RuntimeError, match="ruff format failed"):
            generator_module.format_generated_files(tmp_path / "data.py")


# ============================================================================
# Tests for main() — atomic write (D-05)
# ============================================================================


class TestMainAtomicWrite:
    """Tests for the unique-temp atomic write."""

    def _prepare(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Path, Path]:
        """Point the generator at tmp_path copies of its inputs/outputs."""
        data_file = tmp_path / "themes.jsonl"
        data_file.write_text(json.dumps(_record()) + "\n")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        target = out_dir / "data.py"
        monkeypatch.setattr(generator_module, "DATA_FILE", data_file)
        monkeypatch.setattr(generator_module, "OUTPUT_PATH", target)
        return target, out_dir

    def test_success_replaces_target_and_leaves_no_stray_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful run renames the formatted temp file over the target
        and leaves nothing else in the output directory."""
        target, out_dir = self._prepare(tmp_path, monkeypatch)

        main()

        assert target.exists()
        assert "DO NOT EDIT" in target.read_text()
        assert [p.name for p in out_dir.iterdir()] == ["data.py"]

    def test_interrupted_run_leaves_target_and_directory_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the format step raises, the target is byte-for-byte
        unchanged and no stray temp file survives — the mkstemp name is
        unique per run, so the directory contents are asserted, which also
        proves the finally-cleanup fires when ruff raises."""
        target, out_dir = self._prepare(tmp_path, monkeypatch)
        original = b"# original committed content\n"
        target.write_bytes(original)

        def boom(*paths: Path) -> None:
            raise RuntimeError("ruff exploded")

        monkeypatch.setattr(generator_module, "format_generated_files", boom)

        with pytest.raises(RuntimeError, match="ruff exploded"):
            main()

        assert target.read_bytes() == original
        assert [p.name for p in out_dir.iterdir()] == ["data.py"]

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason=(
            "POSIX permission bits: Windows chmod() only toggles the read-only "
            "flag, so the mode always stats as 0o666 and umask has no meaning. "
            "The behaviour under test only exists on POSIX."
        ),
    )
    @pytest.mark.parametrize("umask_value", [0o022, 0o077])
    def test_generated_module_is_world_readable_under_any_umask(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, umask_value: int
    ) -> None:
        """The generated module lands 0644 whatever the operator's umask.

        mkstemp creates 0600 and Path.replace() carries the temp mode onto
        the target, so a umask-derived mode would ship an owner-only module
        inside the wheel — invisibly, since git tracks only the exec bit.
        """
        target, _ = self._prepare(tmp_path, monkeypatch)
        original_umask = os.umask(umask_value)
        try:
            main()
        finally:
            os.umask(original_umask)

        assert target.stat().st_mode & 0o777 == 0o644

    def test_validation_failure_before_write_leaves_no_temp_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A validation abort never creates the target or any temp file."""
        target, out_dir = self._prepare(tmp_path, monkeypatch)
        data_file = tmp_path / "themes.jsonl"
        data_file.write_text(json.dumps(_record(colors=[])) + "\n")

        with pytest.raises(RuntimeError, match="zero colours"):
            main()

        assert list(out_dir.iterdir()) == []
