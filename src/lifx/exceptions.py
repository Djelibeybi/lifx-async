"""lifx-async exceptions."""

from __future__ import annotations


class LifxError(Exception):
    """Base exception for all lifx-async errors."""

    pass


class LifxDeviceNotFoundError(LifxError):
    """Raised when a device cannot be found or reached.

    Raised by ``Device.from_ip()`` and ``Device.connect()`` when the target
    device does not respond or has an unknown product ID.
    """

    pass


class LifxTimeoutError(LifxError):
    """Raised when an operation times out.

    Raised by the network transport layer when no data is received within the
    timeout period, and by the connection layer when a request receives no
    matching response before the deadline.
    """

    pass


class LifxProtocolError(LifxError):
    """Raised when there's an error with protocol parsing or validation.

    Raised when a packet lacks the required ``PKT_TYPE`` attribute, when
    header deserialization fails, or when a response packet type does not
    match the expected type.
    """

    pass


class LifxConnectionError(LifxError):
    """Raised when there's a connection error.

    Raised when an operation is attempted on a connection that is not open.
    Use the ``async with`` context manager to ensure connections are opened
    and closed correctly.
    """

    pass


class LifxNetworkError(LifxError):
    """Raised when there's a network-level error.

    Raised when the UDP or mDNS socket cannot be opened, when sending or
    receiving data fails at the OS level, or when the socket is not open.
    """

    pass


class LifxUnsupportedCommandError(LifxError):
    """Raised when a device doesn't support the requested command.

    Raised when a device returns a ``StateUnhandled`` response indicating
    the packet type is not supported, or when calling a method that requires
    a capability the device does not have.
    """

    pass
