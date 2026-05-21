"""Unit tests for the pure helpers in macos_control (no system calls)."""
from winter.system.macos_control import VOLUME_STEP, _is_youtube_url


def test_youtube_urls_detected():
    assert _is_youtube_url("https://www.youtube.com/watch?v=abc123")
    assert _is_youtube_url("https://YouTube.com/")
    assert _is_youtube_url("https://m.youtube.com/watch?v=x")
    assert _is_youtube_url("https://youtu.be/abc123")


def test_non_youtube_urls_rejected():
    assert not _is_youtube_url("https://vimeo.com/12345")
    assert not _is_youtube_url("https://www.google.com")
    assert not _is_youtube_url("")
    assert not _is_youtube_url(None)  # type: ignore[arg-type]


def test_volume_step_is_one_notch():
    assert VOLUME_STEP == 100 / 16
