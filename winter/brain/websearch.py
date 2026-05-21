"""Web search for spoken Q&A — DuckDuckGo via ddgs, behind an interface."""
from __future__ import annotations

from abc import ABC, abstractmethod


class WebSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[str]:
        """Return a list of 'title: snippet' strings. Best-effort — [] on failure."""


class DdgsProvider(WebSearchProvider):
    def search(self, query: str, max_results: int = 5) -> list[str]:
        from ddgs import DDGS

        results: list[str] = []
        try:
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results):
                    title = (item.get("title") or "").strip()
                    body = (item.get("body") or "").strip()
                    if body:
                        results.append(f"{title}: {body}" if title else body)
        except Exception:
            return []
        return results
