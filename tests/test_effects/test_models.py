"""Tests for effects models."""

import asyncio

from lifx.color import HSBK
from lifx.effects.base import LIFXEffect
from lifx.effects.models import PreState, RunningEffect


class DummyEffect(LIFXEffect):
    """Dummy effect for testing."""

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "dummy"

    async def async_play(self) -> None:
        """Dummy play method."""
        pass


async def dummy_coroutine() -> None:
    """Dummy coroutine for creating tasks."""
    await asyncio.sleep(0)


def test_prestate_creation():
    """Test creating a PreState instance."""
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    prestate = PreState(power=True, color=color, zone_colors=None)

    assert prestate.power is True
    assert prestate.color == color
    assert prestate.zone_colors is None


def test_prestate_with_zones():
    """Test creating a PreState with zone colors."""
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    zone_colors = [
        HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
        HSBK(hue=60, saturation=1.0, brightness=1.0, kelvin=3500),
        HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
    ]
    prestate = PreState(power=True, color=color, zone_colors=zone_colors)

    assert prestate.power is True
    assert prestate.color == color
    assert prestate.zone_colors == zone_colors
    assert len(prestate.zone_colors) == 3


def test_prestate_repr():
    """Test PreState string representation."""
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    prestate = PreState(power=True, color=color, zone_colors=None)

    repr_str = repr(prestate)
    assert "PreState" in repr_str
    assert "power=True" in repr_str
    assert "no_zones" in repr_str


async def test_running_effect_creation():
    """Test creating a RunningEffect instance."""
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    prestate = PreState(power=True, color=color, zone_colors=None)
    effect = DummyEffect(power_on=True)
    task = asyncio.create_task(dummy_coroutine())
    running = RunningEffect(effect=effect, prestate=prestate, task=task)

    assert running.effect == effect
    assert running.prestate == prestate
    assert running.task == task

    # Clean up
    await task


async def test_running_effect_repr():
    """Test RunningEffect string representation."""
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    prestate = PreState(power=True, color=color, zone_colors=None)
    effect = DummyEffect(power_on=True)
    task = asyncio.create_task(dummy_coroutine())
    running = RunningEffect(effect=effect, prestate=prestate, task=task)

    repr_str = repr(running)
    assert "RunningEffect" in repr_str
    assert "DummyEffect" in repr_str

    # Clean up
    await task
