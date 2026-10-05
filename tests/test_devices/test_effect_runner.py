"""Lights reach their software effects through a registered effect runner."""

from __future__ import annotations

import pytest

from lifx.devices import effect_runner as runner_module
from lifx.devices.effect_runner import effect_runner, register_effect_runner


def test_importing_lifx_registers_the_effect_runner() -> None:
    """The effects package registers its runner when lifx is imported."""
    assert effect_runner() is not None


def test_a_light_without_an_effect_runner_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no runner registered, a light explains what is missing."""
    registered = effect_runner()
    monkeypatch.setattr(runner_module._Registry, "runner", None)

    with pytest.raises(RuntimeError, match="lifx.effects"):
        effect_runner()

    register_effect_runner(registered)
    assert effect_runner() is registered
