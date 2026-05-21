"""Unit tests for YouTube video-id extraction (no network)."""
from winter.brain.youtube import _ANY_ID_RE, _RENDERER_RE, _search_url


def test_search_url_encodes_query():
    url = _search_url("heaven by clairo")
    assert url.startswith("https://www.youtube.com/results?")
    assert "heaven+by+clairo" in url or "heaven%20by%20clairo" in url


def test_renderer_regex_pulls_top_result():
    html = ('garbage{"videoRenderer":{"videoId":"Y3VnGGFNuzc","title":...}}'
            '{"videoRenderer":{"videoId":"dQw4w9WgXcQ"}}')
    match = _RENDERER_RE.search(html)
    assert match and match.group(1) == "Y3VnGGFNuzc"   # first hit wins


def test_fallback_regex_matches_any_video_id():
    assert _ANY_ID_RE.search('"videoId":"abcDEF12345"').group(1) == "abcDEF12345"


def test_no_match_returns_none():
    assert _RENDERER_RE.search("no videos here") is None
    assert _ANY_ID_RE.search("no videos here") is None
