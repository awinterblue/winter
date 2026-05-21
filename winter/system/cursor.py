"""Cursor control — move, click, scroll, dispatched to the OS backend."""
from winter.system.osinfo import IS_MACOS, IS_WINDOWS

if IS_MACOS:
    from winter.system._cursor_macos import (  # noqa: F401
        click, move_to, screen_size, scroll,
    )
elif IS_WINDOWS:
    from winter.system._cursor_windows import (  # noqa: F401
        click, move_to, screen_size, scroll,
    )
else:  # unsupported OS — harmless no-op stubs
    def screen_size() -> tuple[float, float]:
        return 1920.0, 1080.0

    def move_to(x: float, y: float) -> None:
        pass

    def click() -> None:
        pass

    def scroll(lines: int) -> None:
        pass
