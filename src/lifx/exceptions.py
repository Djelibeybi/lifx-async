"""lifx-async exceptions."""

from __future__ import annotations


class LifxError(Exception):
    """Base exception for all lifx-async errors."""

    pass


class LifxDeviceNotFoundError(LifxError):
    """Raised when a device cannot be found or reached."""

    pass


class LifxTimeoutError(LifxError):
    """Raised when an operation times out."""

    pass


class LifxProtocolError(LifxError):
    """Raised when there's an error with protocol parsing or validation."""

    pass


class LifxConnectionError(LifxError):
    """Raised when there's a connection error."""

    pass


class LifxNetworkError(LifxError):
    """Raised when there's a network-level error."""

    pass


class LifxUnsupportedCommandError(LifxError):
    """Raised when a device doesn't support the requested command."""

    pass
