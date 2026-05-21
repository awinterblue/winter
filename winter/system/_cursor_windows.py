"""Move, click, and scroll the Windows cursor via the Win32 API.

UNTESTED on a real Windows machine — written for the Windows port. Cursor
positioning may need DPI-awareness handling on high-DPI displays; verify on
Windows.
"""
from __future__ import annotations

import ctypes

_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_WHEEL = 0x0800
_WHEEL_DELTA = 120   # one notch of the scroll wheel


def screen_size() -> tuple[float, float]:
    """Primary display size in pixels."""
    user32 = ctypes.windll.user32
    return float(user32.GetSystemMetrics(0)), float(user32.GetSystemMetrics(1))


def move_to(x: float, y: float) -> None:
    """Move the cursor to a screen position (in pixels)."""
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def click() -> None:
    """A single left click at the current cursor position."""
    user32 = ctypes.windll.user32
    user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(_MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def scroll(lines: int) -> None:
    """Scroll the wheel vertically: positive scrolls up, negative scrolls down."""
    amount = int(lines) * _WHEEL_DELTA
    ctypes.windll.user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0, amount, 0)
