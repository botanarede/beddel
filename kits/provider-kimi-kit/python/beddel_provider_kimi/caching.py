"""Context caching utilities for provider-kimi-kit.

Provides message separation logic to identify stable system-message prefixes
that can benefit from Kimi's context caching mechanism.
"""

from __future__ import annotations

from typing import Any


def stable_prefix_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Separate system messages as cacheable prefix from dynamic content.

    Kimi's context caching works best when system messages (which rarely
    change between calls) are grouped at the beginning. This function
    identifies the stable system-message prefix and marks it for caching
    by adding cache_control metadata.

    The function is non-destructive: it returns a new list with annotated
    copies of system messages. Non-system messages pass through unchanged.

    Args:
        messages: List of chat messages in OpenAI format.

    Returns:
        Messages with system prefix annotated for caching. If no system
        messages exist at the start, returns the original list unchanged.
    """
    if not messages:
        return messages

    # Find the boundary: consecutive system messages at the start
    prefix_end = 0
    for i, msg in enumerate(messages):
        if msg.get("role") == "system":
            prefix_end = i + 1
        else:
            break

    # No system prefix — return as-is
    if prefix_end == 0:
        return messages

    # Annotate the last system message in the prefix with cache_control
    result: list[dict[str, Any]] = []
    for i, msg in enumerate(messages):
        if i < prefix_end - 1:
            # System messages before the last one — pass through
            result.append(msg)
        elif i == prefix_end - 1:
            # Last system message in prefix — annotate for caching
            annotated = dict(msg)
            annotated["cache_control"] = {"type": "ephemeral"}
            result.append(annotated)
        else:
            # Dynamic content — pass through
            result.append(msg)

    return result
