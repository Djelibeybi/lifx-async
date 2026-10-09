"""Colour generators that turn a theme into colours for a device.

``theme`` holds the gradient generators ``apply_theme()`` uses, ``mood``
the generator ``apply_mood()`` uses, and ``canvas`` the internal ``Canvas``
rendering primitive behind ``MatrixGenerator``.
"""

from __future__ import annotations

from lifx.theme.generators.theme import (
    MatrixGenerator,
    MultiZoneGenerator,
    SingleZoneGenerator,
)

__all__ = [
    "MatrixGenerator",
    "MultiZoneGenerator",
    "SingleZoneGenerator",
]
