"""Windows system control: output volume and media-transport keys.

UNTESTED on a real Windows machine — written for the Windows port; verify
volume control and media keys on Windows before relying on them.
"""
from __future__ import annotations

import ctypes

VOLUME_STEP = 100 / 16   # match the macOS notch size for "volume up/down N"


# --- output volume via the Core Audio API (pycaw) ---
def _endpoint_volume():
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    speakers = AudioUtilities.GetSpeakers()
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> int:
    try:
        return round(_endpoint_volume().GetMasterVolumeLevelScalar() * 100)
    except Exception:  # noqa: BLE001
        return 0


def set_volume(level: int) -> int:
    level = max(0, min(100, int(level)))
    try:
        _endpoint_volume().SetMasterVolumeLevelScalar(level / 100.0, None)
    except Exception:  # noqa: BLE001
        pass
    return level


def change_volume(steps: int) -> int:
    """Raise/lower the volume by `steps` notches; returns the new level."""
    return set_volume(round(get_volume() + steps * VOLUME_STEP))


# --- media keys (Windows virtual key codes) ---
_VK_MEDIA = {
    "play_pause": 0xB3,   # VK_MEDIA_PLAY_PAUSE
    "next": 0xB0,         # VK_MEDIA_NEXT_TRACK
    "previous": 0xB1,     # VK_MEDIA_PREV_TRACK
}
_KEYEVENTF_KEYUP = 0x0002


def _tap_key(vk: int) -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)                  # key down
    user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)   # key up


def media(action: str) -> str | None:
    """Run a media-transport action; returns "media", or None if unknown.

    Windows has no simple way to read the active browser tab's URL, so the
    YouTube-specific 'next video' shortcut isn't offered here — the standard
    media key is used for everything (Music, Spotify, playlists)."""
    vk = _VK_MEDIA.get(action)
    if vk is None:
        return None
    _tap_key(vk)
    return "media"
