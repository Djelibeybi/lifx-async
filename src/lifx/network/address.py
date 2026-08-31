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
  ``Device.connect()`` gate on :func:`validate_address` and
  :func:`validate_port`; the public factories validate caller input once and
  explicitly suppress duplicate constructor advisories
* :mod:`lifx.api`: ``find_by_ip()`` gates on :func:`validate_address`
* :mod:`lifx.network.transport`: ``UdpTransport.open()`` derives its socket
  family with :func:`family_for` and canonicalises its local bind with
  :func:`sockaddr_for`, while ``send()`` canonicalises its destination with
  :func:`sockaddr_for` and derives its family with
  :func:`family_for_sockaddr`
* :mod:`lifx.network.connection`: ``DeviceConnection.open()`` derives its
  bind literal with :func:`wildcard_for` and resolves its destination once
  with :func:`sockaddr_for`
* :mod:`lifx.network.discovery`: discovery derives bind literals with
  :func:`wildcard_for`, reconstructs responder scope with
  :func:`host_from_sockaddr`, and validates wire addresses without emitting
  caller-input warnings; device construction retains that explicit policy
* :mod:`lifx.network.discovery.mdns.discovery`: mDNS validates packet-source and
  advertised device addresses with :func:`validate_address`, suppressing
  caller-input warnings for both wire-controlled paths and for construction
  from those validated records
* :mod:`lifx.animation.animator`: ``Animator`` validates its caller-supplied
  address, resolves its frame destination with :func:`sockaddr_for`, and
  derives the socket family with :func:`family_for_sockaddr`

**The validate/derive split.** :func:`validate_address` is the entry-point
gate and applies the caller-facing rules; :func:`family_for`,
:func:`family_for_sockaddr`, and :func:`wildcard_for` only derive, and
deliberately apply none of them. :func:`sockaddr_for` canonicalises both local
binds and remote destinations; its ``require_routable`` switch applies the
link-local scope rule only to destinations. These operations answer different
questions: ``"::"`` and an unscoped link-local literal are illegal *device*
destinations yet legitimate inputs for a local bind, where the operating
system owns the final decision. The accepted cost is that an address may be
parsed twice when a caller needs more than one answer.

Device ports follow the same centralised shape: remote endpoints must use an
integer in the unprivileged 1024--65535 range, while local binds may additionally
use zero to request an ephemeral port. :func:`sockaddr_for` applies that rule
before a destination reaches operating-system socket handling.

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
5. An IPv6 zone must be printable ASCII. Numeric zones must fit the native
   unsigned 32-bit scope field and cannot be zero; zero means no interface
   scope and would discard the caller's link-local routing intent.
6. An IPv6 link-local address with no zone identifier is rejected. Link-local
   addresses are ambiguous without an interface, so the send silently goes
   nowhere and the caller waits out the full request timeout. Rejecting it
   turns a permanent configuration error into an immediate, named failure.
7. A loopback address is accepted with a warning: a real LIFX device is never
   on loopback, but the test suite legitimately puts an emulator there.
8. A non-private address is accepted with a warning: LIFX devices live on the
   local network, so a routable public address is usually a mistake.

Rules 7 and 8 are caller-input advisories and may be suppressed with
``emit_warnings=False``. Inbound wire validation does this because a responder
controls its source address, so one warning per datagram would itself be a
flooding vector. Device constructors also accept a private, explicit warning
policy: public factories validate once and suppress duplicate constructor
advisories, while discovery factories suppress advisories for already-validated
wire data. The rejections in rules 1-6 are never suppressed.

This is a near-leaf module by design. Its one import from ``lifx`` is
:data:`lifx.const.DEFAULT_IP_ADDRESS`, which :func:`wildcard_for` returns.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Final

from lifx.const import DEFAULT_IP_ADDRESS

_LOGGER = logging.getLogger(__name__)

MIN_DEVICE_PORT: Final[int] = 1024
MAX_PORT: Final[int] = 65535

#: The IPv6 wildcard bind literal, the counterpart to
#: :data:`lifx.const.DEFAULT_IP_ADDRESS` on the IPv6 side. Named here rather
#: than in ``const.py`` because :func:`wildcard_for` is its only consumer.
_IPV6_WILDCARD = "::"
_MAX_SCOPE_ID = 0xFFFFFFFF

SocketAddress = tuple[str, int] | tuple[str, int, int, int]


def _numeric_scope_id(zone: str, ip: str) -> int | None:
    """Validate zone text and return an ASCII numeric scope when present."""
    if not zone.isascii() or not zone.isprintable():
        raise ValueError(f"Invalid IPv6 zone identifier in {ip!r}")

    if not zone.isdecimal():
        return None

    significant = zone.lstrip("0") or "0"
    maximum = str(_MAX_SCOPE_ID)
    if len(significant) > len(maximum) or (
        len(significant) == len(maximum) and significant > maximum
    ):
        raise ValueError(f"IPv6 zone identifier is out of range in {ip!r}")

    scope_id = int(significant)
    if scope_id == 0:
        raise ValueError(f"IPv6 zone identifier must select a non-zero interface: {ip}")
    return scope_id


def _scope_id_for(zone: str, ip: str) -> int:
    """Resolve a validated numeric or named IPv6 zone to an interface index."""
    numeric_scope = _numeric_scope_id(zone, ip)
    if numeric_scope is not None:
        return numeric_scope

    try:
        scope_id = socket.if_nametoindex(zone)
    except (OSError, ValueError, UnicodeError) as error:
        raise ValueError(f"Invalid IPv6 zone identifier {zone!r} in {ip!r}") from error

    if not 1 <= scope_id <= _MAX_SCOPE_ID:
        raise ValueError(f"IPv6 zone identifier is out of range in {ip!r}")
    return scope_id


def _unscoped_ipv6_host(address: ipaddress.IPv6Address) -> str:
    """Return the canonical IPv6 host text without any zone identifier."""
    return str(ipaddress.IPv6Address(address.packed))


def validate_port(port: object, *, allow_zero: bool = False) -> None:
    """Validate a device port or a local ephemeral-bind sentinel.

    Remote LIFX endpoints use the same unprivileged-port range as device
    construction. Local socket binds may additionally request port zero so
    the operating system chooses an ephemeral port.
    """
    if isinstance(port, bool) or not isinstance(port, int):
        raise ValueError(f"Port must be an integer, got {port!r}")

    minimum_port = 0 if allow_zero else MIN_DEVICE_PORT
    if not minimum_port <= port <= MAX_PORT:
        raise ValueError(
            f"Port must be between {minimum_port} and {MAX_PORT}, got {port}"
        )


def sockaddr_for(
    address: SocketAddress, *, require_routable: bool = True
) -> SocketAddress:
    """Return the canonical native sockaddr for an IP endpoint.

    IPv4 endpoints remain two-tuples. IPv6 endpoints always become four-tuples,
    preserving an existing flowinfo/scope pair or resolving a textual zone once.
    Remote link-local destinations require a scope by default; local bind
    callers may defer that routing decision to the operating system.
    """
    host, port = address[0], address[1]
    validate_port(port, allow_zero=not require_routable)
    parsed = ipaddress.ip_address(host)
    if isinstance(parsed, ipaddress.IPv4Address):
        return host, port

    flowinfo = address[2] if len(address) == 4 else 0
    supplied_scope = address[3] if len(address) == 4 else 0
    if not 0 <= supplied_scope <= _MAX_SCOPE_ID:
        raise ValueError(f"IPv6 zone identifier is out of range in {host!r}")

    textual_scope = parsed.scope_id
    if supplied_scope:
        if textual_scope is not None:
            numeric_scope = _numeric_scope_id(textual_scope, host)
            if numeric_scope is not None and numeric_scope != supplied_scope:
                raise ValueError(
                    f"Conflicting IPv6 zone identifiers in {host!r}: "
                    f"text selects {numeric_scope}, sockaddr selects {supplied_scope}"
                )
        scope_id = supplied_scope
    elif textual_scope is not None:
        scope_id = _scope_id_for(textual_scope, host)
    else:
        scope_id = 0

    if require_routable and parsed.is_link_local and scope_id == 0:
        raise ValueError(f"IPv6 link-local address requires a zone identifier: {host}")

    unscoped_host = _unscoped_ipv6_host(parsed)
    return unscoped_host, port, flowinfo, scope_id


def host_from_sockaddr(
    address: SocketAddress, *, fallback_ip: str | None = None
) -> str:
    """Return a host literal that preserves an IPv6 sockaddr's scope.

    A non-zero native numeric scope is authoritative. If a platform supplies
    scope zero, a textual zone already attached to the host is preserved. If
    both are absent for a link-local response, the validated destination's
    textual zone may be used as a fallback so targeted discovery does not
    discard a live response.
    """
    host = address[0]
    if len(address) != 4:
        return host

    parsed = ipaddress.ip_address(host)
    if not isinstance(parsed, ipaddress.IPv6Address):
        return host

    unscoped_host = _unscoped_ipv6_host(parsed)
    if address[3] != 0:
        return f"{unscoped_host}%{address[3]}"

    if parsed.scope_id is not None:
        return str(parsed)

    if parsed.is_link_local and fallback_ip is not None:
        fallback = ipaddress.ip_address(fallback_ip)
        if isinstance(fallback, ipaddress.IPv6Address) and fallback.scope_id:
            return f"{unscoped_host}%{fallback.scope_id}"

    return unscoped_host


def validate_address(ip: str | None, *, emit_warnings: bool = True) -> None:
    """Validate a device address, raising on anything unusable.

    This is the entry-point gate. It is called before any socket exists, so
    a permanent configuration error costs microseconds instead of a full
    request timeout.

    Args:
        ip: The device address to check.
        emit_warnings: Emit caller-facing advisories for loopback and public
            addresses. Inbound wire validation disables these warnings to
            avoid one warning per responder datagram; device factories also
            disable them during construction after validation has already run.

    Raises:
        ValueError: If the address is empty, unparsable, IPv4-mapped,
            unspecified, has a malformed or out-of-range zone identifier, or
            is an IPv6 link-local address with no zone identifier.
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

    if addr.is_unspecified:
        raise ValueError("Unspecified IP address (0.0.0.0) not allowed")

    if isinstance(addr, ipaddress.IPv6Address):
        if addr.scope_id is not None:
            _numeric_scope_id(addr.scope_id, ip)

        if addr.is_link_local and addr.scope_id is None:
            raise ValueError(
                f"IPv6 link-local address requires a zone identifier: {ip}. "
                f"Append the interface, for example {ip}%en0"
            )

    if emit_warnings and addr.is_loopback:
        _LOGGER.warning(
            {
                "module": "lifx.network.address",
                "function": "validate_address",
                "action": "is_loopback",
                "ip": ip,
            }
        )

    if emit_warnings and not addr.is_private:
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


def family_for_sockaddr(address: SocketAddress) -> socket.AddressFamily:
    """Return the socket family implied by a canonical native sockaddr."""
    return socket.AF_INET6 if len(address) == 4 else socket.AF_INET


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
