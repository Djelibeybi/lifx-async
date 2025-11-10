"""Constants for effects framework.

This module defines timing and configuration constants used across the
effects system for consistent behavior.
"""

# Power-on timing constants
POWER_ON_TRANSITION_DURATION = 0.3  # Duration for power-on transition (seconds)
POWER_ON_SETTLE_DELAY = 0.4  # Delay after power-on for device to settle (seconds)

# State restoration timing constants
ZONE_UPDATE_SETTLE_DELAY = 0.3  # Delay after zone color updates (seconds)
COLOR_UPDATE_SETTLE_DELAY = 0.3  # Delay after color updates (seconds)

# Effect timing constants
EFFECT_COMPLETION_BUFFER = 0.1  # Buffer time after effect duration (seconds)

# Color defaults
MIN_VISIBLE_BRIGHTNESS = 0.1  # Minimum brightness considered "visible"
DEFAULT_BRIGHTNESS = 0.8  # Default brightness for powered-off devices
