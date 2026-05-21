"""Permission checks and first-run guidance.

macOS gates input simulation and the camera behind TCC permissions; Windows
does not, so on Windows these checks all report 'granted'.
"""
from __future__ import annotations

from winter.system.osinfo import IS_MACOS


def accessibility_trusted() -> bool:
    """Whether this process may post input events (media keys, cursor control)."""
    if not IS_MACOS:
        return True  # Windows/Linux don't gate input simulation
    try:
        from ApplicationServices import AXIsProcessTrusted
    except Exception:
        return True  # can't check — assume granted rather than nag
    try:
        return bool(AXIsProcessTrusted())
    except Exception:
        return True


def prompt_accessibility() -> bool:
    """Register Winter in the Accessibility list and show the system prompt.

    macOS never auto-prompts for Accessibility (unlike the camera/mic), so an
    app must ask. This adds Winter to System Settings → Privacy & Security →
    Accessibility (switch off) and pops the dialog — the user then only has to
    flip that one switch. Returns the current trusted state.
    """
    if not IS_MACOS:
        return True
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        try:
            from ApplicationServices import kAXTrustedCheckOptionPrompt
            key = kAXTrustedCheckOptionPrompt
        except Exception:
            key = "AXTrustedCheckOptionPrompt"
        return bool(AXIsProcessTrustedWithOptions({key: True}))
    except Exception:
        return accessibility_trusted()


# AVAuthorizationStatus: 0 not-determined, 1 restricted, 2 denied, 3 authorized
def camera_authorized() -> bool:
    """True if the camera is granted (or the status can't be read)."""
    if not IS_MACOS:
        return True
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo

        return AVCaptureDevice.authorizationStatusForMediaType_(
            AVMediaTypeVideo) == 3
    except Exception:
        return True


def camera_access_undecided() -> bool:
    """True only when macOS has never asked the user about the camera."""
    if not IS_MACOS:
        return False
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo

        return AVCaptureDevice.authorizationStatusForMediaType_(
            AVMediaTypeVideo) == 0
    except Exception:
        return False


def request_camera_access() -> None:
    """Trigger the macOS camera-permission prompt. Must run on the main thread."""
    if not IS_MACOS:
        return
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo

        AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVMediaTypeVideo, lambda _granted: None)
    except Exception:
        pass


def permission_hints() -> list[str]:
    """Human-readable warnings for missing permissions."""
    hints: list[str] = []
    if not accessibility_trusted():
        hints.append(
            "Accessibility is OFF — media keys and camera cursor control "
            "won't work. Switch on Winter in System Settings → Privacy & "
            "Security → Accessibility, then restart Winter."
        )
    return hints
