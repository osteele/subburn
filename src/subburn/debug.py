"""Debug utilities."""

from typing import Any

# Default debug level
DEBUG_LEVEL = 0


def set_debug_level(level: int) -> None:
    """Set the debug level."""
    global DEBUG_LEVEL
    DEBUG_LEVEL = level


def debug_print(message: str, *args: Any, level: int = 1) -> None:
    """Print debug messages if debug level is high enough.

    Args:
        message: The message to print
        *args: Additional arguments to format the message with
        level: Debug level required to print this message
    """
    if DEBUG_LEVEL >= level:
        if args:
            print(message.format(*args))
        else:
            print(message)
