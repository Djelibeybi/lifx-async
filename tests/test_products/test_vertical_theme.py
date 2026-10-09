"""Tests for the vertical-theme product quirk."""

from __future__ import annotations

import pytest

from lifx.products import VERTICAL_THEME_PRODUCTS, has_vertical_theme


@pytest.mark.parametrize(
    "pid", [57, 68, 137, 138, 185, 186, 215, 216, 217, 218, 267, 268]
)
def test_vertical_theme_products(pid: int) -> None:
    assert has_vertical_theme(pid)
    assert pid in VERTICAL_THEME_PRODUCTS


@pytest.mark.parametrize("pid", [55, 176, 171, 173, 219, 27])
def test_other_products_are_not_vertical(pid: int) -> None:
    assert not has_vertical_theme(pid)
