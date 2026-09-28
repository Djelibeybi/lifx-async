"""Tests for the deprecated EffectFlame alias of EffectFlicker."""

import pytest

from lifx.effects.flame import EffectFlame
from lifx.effects.flicker import EffectFlicker


def test_flame_warns_deprecation() -> None:
    """Test EffectFlame emits a DeprecationWarning naming EffectFlicker."""
    with pytest.warns(DeprecationWarning, match="EffectFlicker"):
        EffectFlame()


def test_flame_is_flicker_instance() -> None:
    """Test EffectFlame instances are EffectFlicker instances."""
    with pytest.warns(DeprecationWarning):
        effect = EffectFlame()

    assert isinstance(effect, EffectFlicker)
    assert effect.name == "flicker"


def test_flame_behaves_as_flicker() -> None:
    """Test EffectFlame forwards constructor arguments like EffectFlicker."""
    with pytest.warns(DeprecationWarning):
        effect = EffectFlame(intensity=0.5, speed=2.0)

    assert effect.intensity == 0.5
    assert effect.speed == 2.0
