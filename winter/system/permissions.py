"""macOS permission checks and first-run guidance."""
from __future__ import annotations


def accessibility_trusted() -> bool:
    """Whether this process may post input events (media keys, cursor control)."""
    try:
        from ApplicationServices import AXIsProcessTrusted
    except Exception:
        return True  # can't check — assume granted rather than nag
    try:
        return bool(AXIsProcessTrusted())
    except Exception:
        return True


# AVAuthorizationStatus: 0 not-determined, 1 restricted, 2 denied, 3 authorized
def camera_authorized() -> bool:
    """True if the camera is granted (or the status can't be read)."""
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo

        return AVCaptureDevice.authorizationStatusForMediaType_(
            AVMediaTypeVideo) == 3
    except Exception:
        return True


def camera_access_undecided() -> bool:
    """True only when macOS has never asked the user about the camera."""
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo

        return AVCaptureDevice.authorizationStatusForMediaType_(
            AVMediaTypeVideo) == 0
    except Exception:
        return False


def request_camera_access() -> None:
    """Trigger the macOS camera-permission prompt. Must run on the main thread."""
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
            "Accessibility is OFF — media keys won't work. Grant it to your "
            "terminal app: System Settings -> Privacy & Security -> "
            "Accessibility, then restart Winter."
        )
    return hints
