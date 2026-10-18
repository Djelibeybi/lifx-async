"""Tests for the lifx.onboard error base and phase enum."""

from __future__ import annotations

import pytest

from lifx.exceptions import LifxError
from lifx.onboard import LifxOnboardError, MissingCredentialsError, OnboardPhase


def test_phase_members() -> None:
    assert [phase.name for phase in OnboardPhase] == [
        "SCAN",
        "JOIN",
        "WAIT",
        "DIAL",
        "CONFIGURE",
        "REJOIN",
        "VERIFY",
    ]


def test_base_is_a_lifx_error() -> None:
    assert issubclass(LifxOnboardError, LifxError)


def test_phase_and_result_default_to_none() -> None:
    error = LifxOnboardError("boom")
    assert str(error) == "boom"
    assert error.phase is None
    assert error.result is None


def test_phase_and_result_are_exposed() -> None:
    marker = object()
    error = LifxOnboardError("boom", phase=OnboardPhase.JOIN, result=marker)
    assert error.phase is OnboardPhase.JOIN
    assert error.result is marker


def test_missing_credentials_is_also_a_value_error() -> None:
    error = MissingCredentialsError("need a password", phase=OnboardPhase.CONFIGURE)
    assert isinstance(error, LifxOnboardError)
    assert isinstance(error, ValueError)
    assert error.phase is OnboardPhase.CONFIGURE
    with pytest.raises(ValueError):
        raise error
