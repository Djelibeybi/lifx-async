"""The single home of address-family selection and address validation.

Every rule about what a device address may be, and which socket family it
implies, lives here and nowhere else. One rule, stated once, so the call sites
cannot drift apart. That drift is not hypothetical: before this module
existed, the same colon-membership heuristic for "is this IPv6?" was written
out by hand at three separate socket-creation sites, and the address checks
in :meth:`lifx.devices.base.Device.__init__` were a fourth, independent
opinion that the other three never consulted.

The call sites, all of which import from here:

* :mod:`lifx.devices.base`: ``Device.__init__``, ``Device.from_ip()`` and
  ``Device.connect()`` gate on :func:`validate_address`
* :mod:`lifx.api`: ``find_by_ip()`` gates on :func:`validate_address`
* :mod:`lifx.network.transport`: ``UdpTransport.open()`` derives its socket
  family from the local bind address with :func:`family_for`
* :mod:`lifx.network.connection`: ``DeviceConnection._open()`` derives its
  bind literal from the device target with :func:`wildcard_for`, so it
  contains no family test at all
* :mod:`lifx.animation.animator`: ``Animator.send_frame`` derives the frame
  socket's family from the target with :func:`family_for`

**The validate/derive split.** :func:`validate_address` is the entry-point
gate and applies the caller-facing rules; :func:`family_for` and
:func:`wildcard_for` only derive, and deliberately apply none of them. The
two answer different questions: ``"::"`` is an illegal *device* address
(unspecified) yet a perfectly legitimate *local bind* literal, so the
transport must be able to ask for its family without being told it is
invalid. The accepted cost is that an address is parsed twice when a caller
needs both answers.

**The rules, in the order :func:`validate_address` applies them.** Every
rejection is evaluated before either warning, so an address on its way to a
``ValueError`` never logs on the way out:

1. An empty or missing address is rejected, because there is nothing to
   connect to.
2. A literal the stdlib cannot parse is rejected, preserving the original
   ``Invalid IP address format`` wording. An empty zone (``fe80::1%``) fails
   the parse and lands here.
3. An IPv4-mapped IPv6 literal (``::ffff:192.0.2.1``) is rejected. It names
   an IPv4 target in IPv6 clothing, and letting it through would route an
   IPv4 device down the IPv6 socket path.
4. The unspecified address is rejected: it is a wildcard bind, never a
   device.
5. An IPv6 link-local address with no zone identifier is rejected. Link-local
   addresses are ambiguous without an interface, so the send silently goes
   nowhere and the caller waits out the full request timeout. Rejecting it
   turns a permanent configuration error into an immediate, named failure.
6. A loopback address is accepted with a warning: a real LIFX device is never
   on loopback, but the test suite legitimately puts an emulator there.
7. A non-private address is accepted with a warning: LIFX devices live on the
   local network, so a routable public address is usually a mistake.

This is a near-leaf module by design. Its one import from ``lifx`` is
:data:`lifx.const.DEFAULT_IP_ADDRESS`, which :func:`wildcard_for` returns.
"""

from __future__ import annotations

import ipaddress
import logging
import socket

from lifx.const import DEFAULT_IP_ADDRESS

_LOGGER = logging.getLogger(__name__)

#: The IPv6 wildcard bind literal, the counterpart to
#: :data:`lifx.const.DEFAULT_IP_ADDRESS` on the IPv6 side. Named here rather
#: than in ``const.py`` because :func:`wildcard_for` is its only consumer.
_IPV6_WILDCARD = "::"


def validate_address(ip: str | None) -> None:
    """Validate a device address, raising on anything unusable.

    This is the entry-point gate. It is called before any socket exists, so
    a permanent configuration error costs microseconds instead of a full
    request timeout.

    Args:
        ip: The device address to check.

    Raises:
        ValueError: If the address is empty, unparsable, IPv4-mapped,
            unspecified, or an IPv6 link-local address with no zone
            identifier.
    """
    if not ip:
        raise ValueError("No IP address provided")

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as e:
        raise ValueError(f"Invalid IP address format: {e}") from e

    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            raise ValueError(
                f"IPv4-mapped IPv6 address not allowed: {ip}. "
                f"Use the plain IPv4 form instead: {addr.ipv4_mapped}"
            )

        if addr.is_link_local and addr.scope_id is None:
            raise ValueError(
                f"IPv6 link-local address requires a zone identifier: {ip}. "
                f"Append the interface, for example {ip}%en0"
            )

    if addr.is_unspecified:
        raise ValueError("Unspecified IP address (0.0.0.0) not allowed")

    if addr.is_loopback:
        _LOGGER.warning(
            {
                "module": "lifx.network.address",
                "function": "validate_address",
                "action": "is_loopback",
                "ip": ip,
            }
        )

    if not addr.is_private:
        _LOGGER.warning(
            {
                "module": "lifx.network.address",
                "function": "validate_address",
                "action": "non_private_ip",
                "ip": ip,
            }
        )


def family_for(ip: str) -> socket.AddressFamily:
    """Return the socket family an address implies.

    Deliberately applies none of the :func:`validate_address` rules: the
    callers are socket-creation sites, and a local bind literal such as
    ``"::"`` is legitimate there while being an illegal device address.

    Args:
        ip: An IPv4 or IPv6 literal, optionally zoned.

    Returns:
        ``socket.AF_INET6`` for an IPv6 literal, ``socket.AF_INET``
        otherwise.

    Raises:
        ValueError: If the literal cannot be parsed. Propagated unchanged
            from the standard library.
    """
    addr = ipaddress.ip_address(ip)
    return socket.AF_INET6 if addr.version == 6 else socket.AF_INET


def wildcard_for(ip: str) -> str:
    """Return the local wildcard bind literal matching a target address.

    Lets :meth:`lifx.network.connection.DeviceConnection._open` pick its bind
    address without performing a family test of its own.

    Args:
        ip: The device address being connected to.

    Returns:
        ``"::"`` for an IPv6 target, :data:`lifx.const.DEFAULT_IP_ADDRESS`
        otherwise.

    Raises:
        ValueError: If the literal cannot be parsed. Propagated unchanged
            from the standard library.
    """
    return _IPV6_WILDCARD if family_for(ip) == socket.AF_INET6 else DEFAULT_IP_ADDRESS
