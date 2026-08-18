"""The theme data contract lives in the package, not the generator script."""

from __future__ import annotations

from pathlib import Path

import pytest

from lifx.theme.schema import (
    DISPOSITIONS,
    RENAMED,
    canonical_palette,
    load_theme_records,
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


def test_canonical_palette_is_stable_under_reordering() -> None:
    one = [{"hue": 100, "saturation": 1, "brightness": 0.5, "kelvin": 3500}]
    two = [{"kelvin": 3500, "brightness": 0.5, "saturation": 1, "hue": 100}]

    assert canonical_palette(one) == canonical_palette(two)


def test_validate_records_rejects_kelvin_zero() -> None:
    record = {
        "slug": "x",
        "name": "X",
        "category": "Test",
        "disposition": "lifx-app",
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
