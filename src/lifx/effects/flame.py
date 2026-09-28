"""Deprecated alias for the Flicker effect.

The software fire/candle effect was originally named ``EffectFlame``, which
clashed with the firmware :class:`~lifx.protocol.protocol_types.FirmwareEffect`
of the same name run by matrix lights via :meth:`MatrixLight.set_effect`. The
software effect was renamed to :class:`~lifx.effects.flicker.EffectFlicker`;
this module keeps ``EffectFlame`` importable, as a deprecated alias, until the
next major version.
"""

from __future__ import annotations

import warnings
from typing import Any

from lifx.effects.flicker import EffectFlicker


class EffectFlame(EffectFlicker):
    """Deprecated alias of :class:`~lifx.effects.flicker.EffectFlicker`.

    Kept for backwards compatibility until the next major version. Behaves
    exactly like ``EffectFlicker`` (its ``name`` is ``"flicker"``); only the
    class name differs.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise as EffectFlicker, warning that this alias is deprecated.

        Args:
            *args: Forwarded to :class:`EffectFlicker`
            **kwargs: Forwarded to :class:`EffectFlicker`
        """
        warnings.warn(
            "EffectFlame is deprecated; use EffectFlicker instead",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
