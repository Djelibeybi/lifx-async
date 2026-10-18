"""Tests for the lifx.onboard error base and phase enum."""

from __future__ import annotations

import dataclasses

import pytest

import lifx.onboard
from lifx.exceptions import LifxError
from lifx.onboard import (
    HostLeftSoftApError,
    HostRejoinError,
    InvalidSoftApTargetError,
    LegacyTlsUnavailableError,
    LifxOnboardError,
    MissingCredentialsError,
    OnboardPhase,
    Result,
    SoftApDialError,
    SoftApJoinError,
    SoftApNotFoundError,
    SoftApSendError,
    SoftApUnreachableError,
    SoftApWaitTimeoutError,
    VerifyTimeoutError,
    errors,
)


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


@pytest.mark.parametrize(
    ("error_type", "phase"),
    [
        (SoftApUnreachableError, OnboardPhase.DIAL),
        (SoftApDialError, OnboardPhase.DIAL),
        (SoftApSendError, OnboardPhase.CONFIGURE),
        (LegacyTlsUnavailableError, None),
        (SoftApNotFoundError, OnboardPhase.SCAN),
        (SoftApJoinError, OnboardPhase.JOIN),
        (SoftApWaitTimeoutError, OnboardPhase.WAIT),
        (HostLeftSoftApError, OnboardPhase.WAIT),
        (HostRejoinError, OnboardPhase.REJOIN),
        (VerifyTimeoutError, OnboardPhase.VERIFY),
        (InvalidSoftApTargetError, None),
    ],
)
def test_softap_errors_default_their_phase(
    error_type: type[LifxOnboardError], phase: OnboardPhase | None
) -> None:
    error = error_type("boom")
    assert isinstance(error, LifxOnboardError)
    assert error.phase is phase
    assert str(error) == "boom"


def test_softap_error_phase_can_be_overridden() -> None:
    error = SoftApDialError("boom", phase=OnboardPhase.VERIFY)
    assert error.phase is OnboardPhase.VERIFY


def test_softap_errors_are_exported() -> None:
    for name in (
        "SoftApUnreachableError",
        "SoftApDialError",
        "SoftApSendError",
        "LegacyTlsUnavailableError",
        "SoftApNotFoundError",
        "SoftApJoinError",
        "SoftApWaitTimeoutError",
        "HostLeftSoftApError",
        "HostRejoinError",
        "VerifyTimeoutError",
        "InvalidSoftApTargetError",
    ):
        assert name in lifx.onboard.__all__
        assert getattr(lifx.onboard, name) is getattr(errors, name)


def test_result_defaults_describe_an_unverified_success() -> None:
    result = Result(serial=None, verified=False, took=1.5)
    assert result.phase is None
    assert result.error is None
    assert result.host_network is None
    assert "password" not in repr(result)


def test_result_is_frozen() -> None:
    result = Result(serial=None, verified=False, took=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.verified = True  # type: ignore[misc]
