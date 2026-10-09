"""The theme data contract lives in the package, not the generator script."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lifx.theme.schema import (
    DISPOSITIONS,
    RENAMED,
    load_theme_records,
    tag_sort_key,
    validate_key,
    validate_records,
)


def test_load_theme_records_pairs_each_record_with_its_line(tmp_path: Path) -> None:
    data = tmp_path / "themes.jsonl"
    data.write_text(
        '{"slug": "a", "name": "A"}\n{"slug": "b", "name": "B"}\n',
        encoding="utf-8",
    )

    records = load_theme_records(data)

    assert [line for line, _ in records] == [1, 2]
    assert [record["slug"] for _, record in records] == ["a", "b"]


def test_validate_key_rejects_a_python_keyword() -> None:
    assert validate_key("sunrise") is True
    assert validate_key("class") is False


def test_validate_records_rejects_kelvin_zero() -> None:
    record = {
        "slug": "x",
        "name": "X",
        "category": "Test",
        "disposition": "lifx-app",
        "static_mode": "blended",
        "colors": [{"hue": 0, "saturation": 0, "brightness": 1, "kelvin": 0}],
    }

    with pytest.raises(RuntimeError, match="kelvin"):
        validate_records([(1, record)])


def test_contract_constants_are_public() -> None:
    assert RENAMED == "renamed"
    assert "lifx-app" in DISPOSITIONS


def test_schema_is_absent_from_the_public_theme_surface() -> None:
    import lifx.theme

    assert "schema" not in getattr(lifx.theme, "__all__", ())


def _valid_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "slug": "x",
        "name": "X",
        "category": "Test",
        "disposition": "lifx-app",
        "static_mode": "blended",
        "colors": [{"hue": 0, "saturation": 1, "brightness": 1, "kelvin": 3500}],
    }
    record.update(overrides)
    return record


def test_static_mode_is_required() -> None:
    record = _valid_record()
    del record["static_mode"]

    with pytest.raises(RuntimeError, match="missing required field.*static_mode"):
        validate_records([(1, record)])


@pytest.mark.parametrize("value", ["Blended", "grid-static", "", 3, None, "class"])
def test_static_mode_must_be_canonical(value: object) -> None:
    with pytest.raises(RuntimeError, match="static_mode .* is not a canonical"):
        validate_records([(1, _valid_record(static_mode=value))])


def test_unknown_well_formed_modes_are_accepted() -> None:
    validate_records(
        [(1, _valid_record(static_mode="aurora_wash", dynamic_mode="shimmer"))]
    )


def test_dynamic_mode_is_optional() -> None:
    validate_records([(1, _valid_record())])
    validate_records([(1, _valid_record(dynamic_mode="morph"))])


@pytest.mark.parametrize("value", [None, "Morph", "", 7])
def test_dynamic_mode_must_be_canonical_when_present(value: object) -> None:
    with pytest.raises(RuntimeError, match="dynamic_mode .* omit the field"):
        validate_records([(1, _valid_record(dynamic_mode=value))])


def test_tags_are_optional_and_accept_display_strings() -> None:
    validate_records([(1, _valid_record())])
    validate_records([(1, _valid_record(tags=[]))])
    validate_records([(1, _valid_record(tags=["Date night", "Calm"]))])


def test_tags_must_be_a_list() -> None:
    with pytest.raises(RuntimeError, match="'tags' is not a list"):
        validate_records([(1, _valid_record(tags="Calm"))])


@pytest.mark.parametrize("tag", ["", 3, None])
def test_each_tag_must_be_a_non_empty_string(tag: object) -> None:
    with pytest.raises(RuntimeError, match="is not a non-empty string"):
        validate_records([(1, _valid_record(tags=[tag]))])


@pytest.mark.parametrize("tag", ["Calm ", " Calm", "Ca\tlm", "Calm\n"])
def test_tags_must_be_trimmed_and_printable(tag: str) -> None:
    with pytest.raises(RuntimeError, match="surrounding whitespace or non-printable"):
        validate_records([(1, _valid_record(tags=[tag]))])


def test_tags_must_be_ascii() -> None:
    with pytest.raises(RuntimeError, match="non-ASCII"):
        validate_records([(1, _valid_record(tags=["Café"]))])


def test_a_tag_must_normalise_to_a_key() -> None:
    with pytest.raises(RuntimeError, match="normalises to an empty key"):
        validate_records([(1, _valid_record(tags=["!!!"]))])


def test_tags_must_not_collide_within_a_record() -> None:
    with pytest.raises(RuntimeError, match="both normalise to 'date_night'"):
        validate_records([(1, _valid_record(tags=["Date night", "date-night"]))])


def test_a_tag_shared_across_records_is_not_a_key_collision() -> None:
    validate_records(
        [
            (1, _valid_record(slug="a", name="A", tags=["Calm"])),
            (2, _valid_record(slug="b", name="B", tags=["Calm"])),
        ]
    )


def test_a_tag_may_equal_a_theme_slug() -> None:
    validate_records(
        [
            (1, _valid_record(slug="calm", name="Calm")),
            (2, _valid_record(slug="b", name="B", tags=["calm"])),
        ]
    )


def test_tag_sort_key_is_case_insensitive_then_exact() -> None:
    tags = ["calm", "Bright", "aqua", "Calm"]

    assert sorted(tags, key=tag_sort_key) == ["aqua", "Bright", "Calm", "calm"]


def test_unicode_name_is_optional() -> None:
    validate_records([(1, _valid_record())])


def test_unicode_name_that_folds_to_name_is_accepted() -> None:
    validate_records(
        [(1, _valid_record(slug="curacao", name="Curacao", unicode_name="Curaçao"))]
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (7, "field 'unicode_name' is not a string"),
        ("", "field 'unicode_name' is empty"),
        ("Curacao", "field 'unicode_name' is ASCII"),
        # Decomposed: "c" plus U+0327 COMBINING CEDILLA, not precomposed "ç".
        ("Curac\u0327ao", "field 'unicode_name' is not NFC-normalised"),
        ("Curaçaoo", "field 'unicode_name' does not fold to name"),
        ("Curaçao 🇨🇼", "field 'unicode_name' does not fold to name"),
    ],
)
def test_invalid_unicode_name_is_rejected(value: object, message: str) -> None:
    record = _valid_record(slug="curacao", name="Curacao", unicode_name=value)
    with pytest.raises(RuntimeError, match=message):
        validate_records([(1, record)])
