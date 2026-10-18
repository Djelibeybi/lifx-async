"""Value types describing the networks involved in onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from lifx.onboard.errors import MissingCredentialsError
from lifx.protocol.models import LIFX_OUI, Serial

_MAX_SSID_BYTES = 32
_MAX_PASSWORD_BYTES = 64


# TODO(#329): replace with lifx.protocol.protocol_types.WifiSecurity once
# ticket 327 is merged.
class WifiSecurity(IntEnum):
    """Wi-Fi security modes understood by packet 305."""

    UNKNOWN = 0
    OPEN = 1
    WEP_PSK = 2
    WPA_TKIP_PSK = 3
    WPA_AES_PSK = 4
    WPA2_AES_PSK = 5
    WPA2_TKIP_PSK = 6
    WPA2_MIXED_PSK = 7


@dataclass(frozen=True)
class SoftApNetwork:
    """A Wi-Fi network seen while scanning, usually a LIFX SoftAP.

    Attributes:
        ssid: Network name.
        serial: Serial derived from the name, or ``None`` for a foreign network.
        bssid: Lowercase colon-separated hardware address.
        rssi: Signal strength, ``0.0`` when the backend cannot report one.
    """

    ssid: str
    serial: Serial | None
    bssid: str
    rssi: float = 0.0

    @classmethod
    def from_ssid(cls, ssid: str, rssi: float = 0.0) -> SoftApNetwork:
        """Build a network from a LIFX SoftAP name.

        Raises:
            ValueError: If ``ssid`` is not a LIFX SoftAP name.
        """
        serial = Serial.from_softap_ssid(ssid)
        bssid = ":".join(f"{octet:02x}" for octet in LIFX_OUI + serial.value[3:])
        return cls(ssid=ssid, serial=serial, bssid=bssid, rssi=rssi)

    @classmethod
    def foreign(cls, ssid: str, bssid: str, rssi: float = 0.0) -> SoftApNetwork:
        """Build a network that is not a LIFX SoftAP (no serial)."""
        return cls(ssid=ssid, serial=None, bssid=bssid.lower(), rssi=rssi)


@dataclass(frozen=True, repr=False)
class HomeNetwork:
    """The network a device should join.

    ``security`` defaults to OPEN for an empty password and WPA2_AES_PSK
    otherwise. The password is never shown by ``repr`` or ``str``, but is part
    of equality.

    Raises:
        ValueError: If the SSID is empty or over 32 UTF-8 bytes, or the
            password is over 64 UTF-8 bytes. Nothing is truncated.
        MissingCredentialsError: If a secured mode is given with no password.
    """

    ssid: str
    password: str = ""
    security: WifiSecurity | int | None = None

    def __post_init__(self) -> None:
        if not self.ssid:
            raise ValueError("Home network SSID must not be empty")
        if len(self.ssid.encode("utf-8")) > _MAX_SSID_BYTES:
            raise ValueError(f"Home network SSID exceeds {_MAX_SSID_BYTES} bytes")
        if len(self.password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Home network password exceeds {_MAX_PASSWORD_BYTES} bytes"
            )
        if self.security is None:
            resolved = WifiSecurity.WPA2_AES_PSK if self.password else WifiSecurity.OPEN
        else:
            resolved = WifiSecurity(self.security)
        if resolved is not WifiSecurity.OPEN and not self.password:
            raise MissingCredentialsError(
                f"Security {resolved.name} requires a password"
            )
        object.__setattr__(self, "security", resolved)

    def __repr__(self) -> str:
        return (
            f"HomeNetwork(ssid={self.ssid!r}, password=<redacted>, "
            f"security={self.security!r})"
        )

    __str__ = __repr__
