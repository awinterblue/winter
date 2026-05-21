"""System control — output volume and media keys, dispatched to the OS backend."""
from winter.system.osinfo import IS_MACOS, IS_WINDOWS

if IS_MACOS:
    from winter.system._control_macos import (  # noqa: F401
        change_volume, get_volume, media, set_volume,
    )
elif IS_WINDOWS:
    from winter.system._control_windows import (  # noqa: F401
        change_volume, get_volume, media, set_volume,
    )
else:  # unsupported OS — harmless no-op stubs
    def get_volume() -> int:
        return 0

    def set_volume(level: int) -> int:
        return 0

    def change_volume(steps: int) -> int:
        return 0

    def media(action: str):
        return None
