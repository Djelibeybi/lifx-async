"""Tests for the shared address rules (`lifx.network.address`).

The module is a leaf rule with three public functions, so every branch is
reachable directly rather than through a ``Device`` constructor. That is the
whole point of the move (D-04): the coverage-exemption markers the rules
carried while they were inline in ``Device.__init__`` come off, and each
branch is exercised from both sides here.

Two orderings matter and are asserted explicitly:

* every rejection is evaluated before either warning, so an address on its
  way to a ``ValueError`` never logs (review finding 11); and
* :func:`family_for` deliberately does *not* apply the entry-point rules, so
  bind literals like ``"::"`` resolve to a family instead of raising.
"""

from __future__ import annotations

import logging
import socket
from unittest.mock import patch

import pytest

from lifx.const import DEFAULT_IP_ADDRESS
from lifx.network.address import (
    family_for,
    host_from_sockaddr,
    sockaddr_for,
    validate_address,
    wildcard_for,
)

_LOGGER_NAME = "lifx.network.address"


class TestValidateAddressRejects:
    """Every arm of `validate_address` that raises."""

    @pytest.mark.parametrize("value", [None, ""])
    def test_empty_or_missing_raises(self, value: str | None) -> None:
        """An absent address names itself in the message."""
        with pytest.raises(ValueError, match="No IP address"):
            validate_address(value)

    def test_malformed_raises_with_the_preserved_message(self) -> None:
        """The wording moved from Device.__init__ unchanged."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_address("not-an-ip")

    def test_empty_zone_raises(self) -> None:
        """`fe80::1%` fails the parse, so it lands on the malformed arm."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_address("fe80::1%")

    @pytest.mark.parametrize(
        "value",
        ["fe80::1", "FE80::1", "fe80:0:0:0:0:0:0:1"],
    )
    def test_zone_less_link_local_raises_naming_the_zone(self, value: str) -> None:
        """Case and expansion are the helper's problem, not the caller's.

        All three spellings are the same address, so all three raise the same
        way. This is the IPV6-02 flip: the branch logged a warning here and
        then spent 16 silent seconds timing out.
        """
        with pytest.raises(ValueError, match="zone"):
            validate_address(value)

    def test_ipv4_mapped_raises(self) -> None:
        """An IPv4 target must not be smuggled in through IPv6 syntax."""
        with pytest.raises(ValueError, match="IPv4-mapped"):
            validate_address("::ffff:192.0.2.1")

    @pytest.mark.parametrize(
        "value",
        [
            "fe80::1%\u0667",
            "fe80::1%a\x00b",
            "fe80::1%\ud800",
        ],
    )
    def test_invalid_zone_text_raises_a_named_validation_error(
        self, value: str
    ) -> None:
        """Malformed zone text never leaks a codec or socket exception."""
        with pytest.raises(ValueError, match="zone identifier"):
            validate_address(value)

    @pytest.mark.parametrize(
        "value",
        [
            f"fe80::1%{2**32}",
            "fe80::1%" + "9" * 5000,
        ],
    )
    def test_out_of_range_numeric_zone_raises_a_named_validation_error(
        self, value: str
    ) -> None:
        """Oversized numeric scopes fail without calling ``int`` unsafely."""
        with pytest.raises(ValueError, match="zone identifier"):
            validate_address(value)

    @pytest.mark.parametrize("value", ["0.0.0.0", "::"])
    def test_unspecified_raises(self, value: str) -> None:
        """The rule moved from Device.__init__, message intact."""
        with pytest.raises(ValueError, match="Unspecified IP address"):
            validate_address(value)


class TestValidateAddressRaisesBeforeWarning:
    """Review finding 11: a doomed address must not log on its way out."""

    @pytest.mark.parametrize("value", ["::ffff:8.8.8.8", "0.0.0.0", "::"])
    def test_rejected_address_logs_nothing(
        self, value: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Each of these would trip a warning arm under the old ordering.

        ``::ffff:8.8.8.8`` is non-private and would have warned before the
        IPv4-mapped rejection; ``0.0.0.0`` and ``::`` are reached only after
        the loopback test under the branch's ordering.
        """
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            with pytest.raises(ValueError):
                validate_address(value)

        assert caplog.records == []


class TestValidateAddressWarns:
    """The two arms that log and return rather than raising."""

    @pytest.mark.parametrize("value", ["127.0.0.1", "::1"])
    def test_loopback_warns_in_the_helper_shape(
        self, value: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The dict names the helper, not the calling class (D-06)."""
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            validate_address(value)

        assert len(caplog.records) == 1
        assert caplog.records[0].msg == {
            "module": "lifx.network.address",
            "function": "validate_address",
            "action": "is_loopback",
            "ip": value,
        }

    def test_non_private_warns_in_the_helper_shape(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A routable public address is legal but worth flagging."""
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            validate_address("8.8.8.8")

        assert len(caplog.records) == 1
        assert caplog.records[0].msg == {
            "module": "lifx.network.address",
            "function": "validate_address",
            "action": "non_private_ip",
            "ip": "8.8.8.8",
        }

    def test_warning_dicts_drop_the_class_and_method_keys(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """D-06 explicitly retires the Device-shaped context keys."""
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            validate_address("127.0.0.1")

        payload = caplog.records[0].msg
        assert isinstance(payload, dict)
        assert "class" not in payload
        assert "method" not in payload


class TestValidateAddressAccepts:
    """Addresses that pass, with and without a log line."""

    @pytest.mark.parametrize(
        "value",
        ["192.168.1.10", "fd00:1::", "fe80::1%en0"],
    )
    def test_private_address_passes_silently(
        self, value: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A zoned link-local is exactly what IPV6-02 wants accepted."""
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            assert validate_address(value) is None

        assert caplog.records == []


class TestSocketAddressConversion:
    """Native socket tuples preserve valid IPv6 scope information."""

    @pytest.mark.parametrize("resolved_scope", [0, 2**32])
    def test_named_zone_resolving_out_of_range_raises(
        self, resolved_scope: int
    ) -> None:
        """Platform interface lookup cannot supply an unusable scope ID."""
        with patch(
            "lifx.network.address.socket.if_nametoindex",
            return_value=resolved_scope,
        ):
            with pytest.raises(ValueError, match="out of range"):
                sockaddr_for(("fe80::1%test0", 56700))

    @pytest.mark.parametrize("scope_id", [-1, 2**32])
    def test_supplied_scope_out_of_range_raises(self, scope_id: int) -> None:
        """A caller-supplied native scope must fit the platform field."""
        with pytest.raises(ValueError, match="out of range"):
            sockaddr_for(("fe80::1", 56700, 0, scope_id))

    def test_already_scoped_native_host_is_preserved(self) -> None:
        """A four-tuple does not append a second zone to a scoped host."""
        assert host_from_sockaddr(("fe80::1%7", 56700, 0, 7)) == "fe80::1%7"


class TestFamilyFor:
    """The derive side: no entry-point rules applied."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("192.168.1.10", socket.AF_INET),
            (DEFAULT_IP_ADDRESS, socket.AF_INET),
            ("fd00:1::", socket.AF_INET6),
            ("fe80::1%en0", socket.AF_INET6),
            ("::1", socket.AF_INET6),
        ],
    )
    def test_family_follows_the_address_version(
        self, value: str, expected: socket.AddressFamily
    ) -> None:
        """Version 6 gives AF_INET6, everything else AF_INET."""
        assert family_for(value) == expected

    def test_wildcard_spellings_agree(self) -> None:
        """SPEC AC 7: the two spellings of the IPv6 wildcard are one address."""
        assert family_for("::") == family_for("0:0:0:0:0:0:0:0") == socket.AF_INET6

    def test_bind_literals_are_not_rejected(self) -> None:
        """`family_for` deliberately skips the validate_address rules.

        ``"::"`` is unspecified, which `validate_address` rejects, yet it is a
        legitimate local bind literal. The split is the accepted cost of D-02.
        """
        assert family_for("::") == socket.AF_INET6
        with pytest.raises(ValueError):
            validate_address("::")

    def test_malformed_propagates_value_error(self) -> None:
        """A caller passing rubbish gets the stdlib parse failure."""
        with pytest.raises(ValueError):
            family_for("bogus")


class TestWildcardFor:
    """The bind literal DeviceConnection._open() needs."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("fdc6::1", "::"),
            ("fe80::1%en0", "::"),
            ("192.168.1.10", DEFAULT_IP_ADDRESS),
        ],
    )
    def test_wildcard_follows_the_family(self, value: str, expected: str) -> None:
        """An IPv6 target binds the IPv6 wildcard, IPv4 the IPv4 one."""
        assert wildcard_for(value) == expected
