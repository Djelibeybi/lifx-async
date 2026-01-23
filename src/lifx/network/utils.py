"""Network utilities for LIFX protocol communication."""

import secrets


def allocate_source() -> int:
    """Allocate unique source identifier for a LIFX protocol request.

    LIFX protocol defines source as Uint32, with 0 and 1 reserved.
    We generate values in range [2, 0xFFFFFFFF].

    Returns:
        Unique source identifier (range: 2 to 4294967295)
    """
    return secrets.randbelow(0xFFFFFFFF - 1) + 2
