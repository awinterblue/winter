"""Move, click, and scroll the macOS cursor via Quartz events.

Posting these events needs Accessibility permission; without it the calls
silently do nothing.
"""
from __future__ import annotations

import Quartz

_pos = {"x": 0.0, "y": 0.0}


def screen_size() -> tuple[float, float]:
    """Main display size in points — the coordinate space Quartz events use."""
    bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    return float(bounds.size.width), float(bounds.size.height)


def _post_mouse(event_type, x: float, y: float) -> None:
    event = Quartz.CGEventCreateMouseEvent(
        None, event_type, (x, y), Quartz.kCGMouseButtonLeft,
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def move_to(x: float, y: float) -> None:
    """Move the cursor to a screen position (in points)."""
    _pos["x"], _pos["y"] = x, y
    _post_mouse(Quartz.kCGEventMouseMoved, x, y)


def click() -> None:
    """A single left click at the current cursor position."""
    x, y = _pos["x"], _pos["y"]
    _post_mouse(Quartz.kCGEventLeftMouseDown, x, y)
    _post_mouse(Quartz.kCGEventLeftMouseUp, x, y)


def scroll(lines: int) -> None:
    """Scroll the wheel vertically: positive scrolls up, negative scrolls down."""
    event = Quartz.CGEventCreateScrollWheelEvent(
        None, Quartz.kCGScrollEventUnitLine, 1, int(lines),
    )
    if event:
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
