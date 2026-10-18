"""Tests for lifx.onboard network models."""

from __future__ import annotations

import dataclasses

import pytest

from lifx.onboard import (
    HomeNetwork,
    MissingCredentialsError,
    SoftApNetwork,
)
from lifx.onboard.models import WifiSecurity
from lifx.protocol.models import Serial

PASSWORD = "hunter2-synthetic"


class TestWifiSecurity:
    def test_values(self) -> None:
        assert {member.name: int(member) for member in WifiSecurity} == {
            "UNKNOWN": 0,
            "OPEN": 1,
            "WEP_PSK": 2,
            "WPA_TKIP_PSK": 3,
            "WPA_AES_PSK": 4,
            "WPA2_AES_PSK": 5,
            "WPA2_TKIP_PSK": 6,
            "WPA2_MIXED_PSK": 7,
        }


class TestSoftApNetwork:
    def test_from_ssid_derives_serial_and_bssid(self) -> None:
        network = SoftApNetwork.from_ssid("LIFX Candle Color 8274eb", rssi=-48.5)
        assert network.ssid == "LIFX Candle Color 8274eb"
        assert network.serial == Serial.from_string("d073d58274eb")
        assert network.bssid == "d0:73:d5:82:74:eb"
        assert network.rssi == -48.5

    def test_rssi_defaults_to_zero(self) -> None:
        assert SoftApNetwork.from_ssid("LIFX 8274EB").rssi == 0.0

    def test_from_ssid_rejects_foreign_name(self) -> None:
        with pytest.raises(ValueError):
            SoftApNetwork.from_ssid("Neighbour4C0A17")

    def test_foreign_network_has_no_serial(self) -> None:
        network = SoftApNetwork.foreign("Neighbour4C0A17", "AA:BB:CC:4C:0A:17", -70.0)
        assert network.serial is None
        assert network.bssid == "aa:bb:cc:4c:0a:17"
        assert network.rssi == -70.0

    def test_foreign_rssi_default(self) -> None:
        assert SoftApNetwork.foreign("x", "aa:bb:cc:4c:0a:17").rssi == 0.0

    def test_is_frozen(self) -> None:
        network = SoftApNetwork.from_ssid("LIFX 8274eb")
        with pytest.raises(dataclasses.FrozenInstanceError):
            network.ssid = "other"  # type: ignore[misc]


class TestHomeNetworkSecurity:
    def test_empty_password_is_open(self) -> None:
        assert HomeNetwork("home").security is WifiSecurity.OPEN

    def test_password_defaults_to_wpa2_aes(self) -> None:
        assert HomeNetwork("home", PASSWORD).security is WifiSecurity.WPA2_AES_PSK

    def test_explicit_security_is_kept(self) -> None:
        network = HomeNetwork("home", PASSWORD, WifiSecurity.WPA2_MIXED_PSK)
        assert network.security is WifiSecurity.WPA2_MIXED_PSK

    def test_integer_security_is_resolved(self) -> None:
        network = HomeNetwork("home", PASSWORD, 3)
        assert network.security is WifiSecurity.WPA_TKIP_PSK

    def test_explicit_open_with_password_is_allowed(self) -> None:
        assert HomeNetwork("home", PASSWORD, 1).security is WifiSecurity.OPEN

    def test_unknown_integer_security_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            HomeNetwork("home", PASSWORD, 99)

    def test_secured_without_password_is_rejected(self) -> None:
        with pytest.raises(MissingCredentialsError) as caught:
            HomeNetwork("home", "", WifiSecurity.WPA2_AES_PSK)
        assert isinstance(caught.value, ValueError)


class TestHomeNetworkLimits:
    def test_empty_ssid_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            HomeNetwork("")

    def test_ssid_at_limit(self) -> None:
        assert HomeNetwork("a" * 32).ssid == "a" * 32

    def test_ssid_over_limit(self) -> None:
        with pytest.raises(ValueError):
            HomeNetwork("a" * 33)

    def test_ssid_limit_counts_utf8_bytes(self) -> None:
        # 16 two-byte characters are exactly 32 bytes; 17 are 34.
        assert HomeNetwork("é" * 16).ssid == "é" * 16
        with pytest.raises(ValueError):
            HomeNetwork("é" * 17)

    def test_ssid_four_byte_characters(self) -> None:
        assert HomeNetwork("😀" * 8).ssid == "😀" * 8
        with pytest.raises(ValueError):
            HomeNetwork("😀" * 9)

    def test_password_at_limit(self) -> None:
        assert HomeNetwork("home", "p" * 64).password == "p" * 64

    def test_password_over_limit(self) -> None:
        with pytest.raises(ValueError):
            HomeNetwork("home", "p" * 65)

    def test_password_limit_counts_utf8_bytes(self) -> None:
        assert HomeNetwork("home", "é" * 32).password == "é" * 32
        with pytest.raises(ValueError):
            HomeNetwork("home", "é" * 33)

    def test_limit_errors_do_not_leak_the_password(self) -> None:
        secret = "s3cret-" + "p" * 70
        with pytest.raises(ValueError) as caught:
            HomeNetwork("home", secret)
        assert secret not in str(caught.value)
        assert "s3cret" not in str(caught.value)

    def test_missing_credentials_message_has_no_password(self) -> None:
        with pytest.raises(MissingCredentialsError) as caught:
            HomeNetwork("home", "", 5)
        assert PASSWORD not in str(caught.value)


class TestHomeNetworkSecrecy:
    def test_repr_and_str_elide_password(self) -> None:
        network = HomeNetwork("home", PASSWORD)
        expected = (
            "HomeNetwork(ssid='home', password=<redacted>, "
            "security=<WifiSecurity.WPA2_AES_PSK: 5>)"
        )
        assert repr(network) == expected
        assert str(network) == expected
        assert PASSWORD not in repr(network)
        assert PASSWORD not in str(network)
        assert PASSWORD not in f"{network!r} {network}"

    def test_open_network_repr(self) -> None:
        assert "password=<redacted>" in repr(HomeNetwork("home"))

    def test_different_passwords_are_unequal(self) -> None:
        assert HomeNetwork("home", "one-password") != HomeNetwork(
            "home", "two-password"
        )

    def test_same_values_are_equal(self) -> None:
        assert HomeNetwork("home", PASSWORD) == HomeNetwork(
            "home", PASSWORD, WifiSecurity.WPA2_AES_PSK
        )

    def test_is_frozen(self) -> None:
        network = HomeNetwork("home")
        with pytest.raises(dataclasses.FrozenInstanceError):
            network.ssid = "other"  # type: ignore[misc]
