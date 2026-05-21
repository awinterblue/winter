"""Find and play YouTube videos by search query — no API key required.

It fetches YouTube's own search-results page and pulls the top video's id out
of the embedded data, then opens it in the default browser.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
import webbrowser
from typing import Optional

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# the first real search hit is the first `videoRenderer`; the loose pattern is
# a fallback in case YouTube tweaks its markup
_RENDERER_RE = re.compile(r'"videoRenderer":\{"videoId":"([\w-]{11})"')
_ANY_ID_RE = re.compile(r'"videoId":"([\w-]{11})"')


def _search_url(query: str) -> str:
    params = urllib.parse.urlencode({"search_query": query, "hl": "en", "gl": "US"})
    return f"https://www.youtube.com/results?{params}"


def find_video(query: str) -> Optional[str]:
    """Return the 11-char id of the top YouTube hit for `query`, or None."""
    request = urllib.request.Request(_search_url(query), headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            html = response.read().decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001 - network/parse failures handled by caller
        return None
    match = _RENDERER_RE.search(html) or _ANY_ID_RE.search(html)
    return match.group(1) if match else None


def play(query: str) -> bool:
    """Open the top YouTube video for `query` in the browser.

    Returns True if a specific video was found and opened; False if it fell
    back to opening the YouTube search page instead.
    """
    video_id = find_video(query)
    if video_id:
        url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        url = _search_url(query)
    webbrowser.open(url)   # cross-platform: opens the default browser
    return video_id is not None
