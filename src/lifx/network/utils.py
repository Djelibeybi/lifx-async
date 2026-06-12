"""Network utilities for LIFX protocol communication."""

import secrets
import time


def allocate_source() -> int:
    """Allocate unique source identifier for a LIFX protocol request.

    LIFX protocol defines source as Uint32, with 0 and 1 reserved.
    We generate values in range [2, 0xFFFFFFFF].

    Returns:
        Unique source identifier (range: 2 to 4294967295)
    """
    return secrets.randbelow(0xFFFFFFFF - 1) + 2


class IdleDeadline:
    """Manages a dual deadline comprising an overall timeout and an idle timeout.

    The overall deadline expires a fixed duration after construction.  The idle
    deadline expires when no call to ``mark_response()`` has been made within
    ``idle_timeout`` seconds.  ``remaining()`` returns the minimum of the two
    remaining durations so a discovery loop can safely pass the result as a
    receive-timeout without overshooting either boundary.

    Uses ``time.monotonic()`` exclusively — never wall-clock time — so the
    calculations are immune to system-clock adjustments.

    Example::

        deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
        while not deadline.expired:
            remaining = deadline.remaining()
            if remaining <= 0:
                break
            data = await transport.receive(timeout=remaining)
            deadline.mark_response()
    """

    def __init__(self, timeout: float, idle_timeout: float) -> None:
        """Initialise with an overall *timeout* and a per-response *idle_timeout*.

        Args:
            timeout: Maximum total duration in seconds before the deadline expires.
            idle_timeout: Maximum duration in seconds between responses before the
                idle deadline expires.
        """
        self._start: float = time.monotonic()
        self._overall: float = timeout
        self._idle: float = idle_timeout
        self._last_response: float = self._start

    def remaining(self) -> float:
        """Return seconds until the next deadline fires.

        Reads ``time.monotonic()`` once per call and returns the minimum of the
        overall remaining time and the idle remaining time.  A return value <=
        0 means at least one deadline has been exceeded.

        Returns:
            Seconds until the sooner deadline; non-positive when expired.
        """
        now = time.monotonic()
        remaining_overall = self._overall - (now - self._start)
        remaining_idle = self._idle - (now - self._last_response)
        return min(remaining_overall, remaining_idle)

    def mark_response(self) -> None:
        """Reset the idle clock to the current monotonic time.

        Call this whenever a valid response is received so that the idle
        deadline extends from *now* rather than from the previous response (or
        from construction if no prior response has been received).
        """
        self._last_response = time.monotonic()

    @property
    def idle_expired(self) -> bool:
        """True when the idle window since the last response has been exceeded."""
        return (time.monotonic() - self._last_response) >= self._idle

    @property
    def overall_expired(self) -> bool:
        """True when the overall timeout since construction has been exceeded."""
        return (time.monotonic() - self._start) >= self._overall

    @property
    def expired(self) -> bool:
        """True when either the idle deadline or the overall deadline has fired."""
        return self.idle_expired or self.overall_expired
