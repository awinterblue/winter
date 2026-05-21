"""macOS system control: output volume and media-transport keys."""
from __future__ import annotations

import subprocess

VOLUME_STEP = 100 / 16  # one macOS volume "notch"


def _osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip()


def get_volume() -> int:
    try:
        return int(_osascript("output volume of (get volume settings)"))
    except (ValueError, subprocess.SubprocessError):
        return 0


def set_volume(level: int) -> int:
    level = max(0, min(100, int(level)))
    _osascript(f"set volume output volume {level}")
    return level


def change_volume(steps: int) -> int:
    """Raise/lower the volume by `steps` notches; returns the new level."""
    return set_volume(round(get_volume() + steps * VOLUME_STEP))


# --- media keys (system-defined Quartz events) ---
_NX_KEYTYPE_PLAY = 16
_NX_KEYTYPE_NEXT = 17
_NX_KEYTYPE_PREVIOUS = 18
_NSSYSTEMDEFINED = 14

_MEDIA_KEYS = {
    "play_pause": _NX_KEYTYPE_PLAY,
    "next": _NX_KEYTYPE_NEXT,
    "previous": _NX_KEYTYPE_PREVIOUS,
}


def _post_media_key(key: int) -> None:
    """Post a system-defined media key event (down then up).

    Requires Accessibility permission. Controls whichever app currently owns
    the media keys (Music, Spotify, a browser video, ...).
    """
    from AppKit import NSEvent
    import Quartz

    for is_down in (True, False):
        flags = 0xA00 if is_down else 0xB00
        data1 = (key << 16) | ((0xA if is_down else 0xB) << 8)
        event = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            _NSSYSTEMDEFINED, (0, 0), flags, 0, 0, None, 8, data1, -1,
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event.CGEvent())


# --- browser / YouTube awareness ---
# YouTube's "next video" autoplay cannot be reached by the media key, so when a
# browser showing YouTube is frontmost we send YouTube's own keyboard shortcut.
_SAFARI_IDS = {"com.apple.Safari", "com.apple.SafariTechnologyPreview"}
_CHROMIUM_IDS = {
    "com.google.Chrome", "com.google.Chrome.canary", "com.brave.Browser",
    "com.microsoft.edgemac", "company.thebrowser.Browser",
    "com.vivaldi.Vivaldi", "com.operasoftware.Opera",
}

_KEYCODE_N = 45  # YouTube: Shift+N = next video
_KEYCODE_P = 35  # YouTube: Shift+P = previous video
_YOUTUBE_NAV = {"next": _KEYCODE_N, "previous": _KEYCODE_P}


def _is_youtube_url(url: str) -> bool:
    url = (url or "").lower()
    return "youtube.com" in url or "youtu.be" in url


def _frontmost_bundle_id() -> str:
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return (app.bundleIdentifier() or "") if app else ""
    except Exception:
        return ""


def _browser_current_url(bundle_id: str) -> str:
    """Best-effort current-tab URL of a frontmost browser.

    Needs macOS Automation permission; returns "" on any failure (including
    Firefox, which exposes no usable AppleScript URL access).
    """
    if bundle_id in _SAFARI_IDS:
        tab = "current tab"
    elif bundle_id in _CHROMIUM_IDS:
        tab = "active tab"
    else:
        return ""
    script = f'tell application id "{bundle_id}" to return URL of {tab} of front window'
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=4)
        return result.stdout.strip()
    except subprocess.SubprocessError:
        return ""


def _youtube_is_frontmost() -> bool:
    bundle_id = _frontmost_bundle_id()
    if not bundle_id:
        return False
    return _is_youtube_url(_browser_current_url(bundle_id))


def _post_shift_key(keycode: int) -> None:
    """Send Shift+<key> to the frontmost app. Requires Accessibility permission."""
    import Quartz

    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for is_down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(source, keycode, is_down)
        Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskShift)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def media(action: str) -> str | None:
    """Run a media-transport action.

    Returns the method used — "youtube" (YouTube keyboard shortcut) or
    "media" (system media key) — or None for an unknown action.
    """
    if action in _YOUTUBE_NAV and _youtube_is_frontmost():
        _post_shift_key(_YOUTUBE_NAV[action])
        return "youtube"
    key = _MEDIA_KEYS.get(action)
    if key is not None:
        _post_media_key(key)
        return "media"
    return None
