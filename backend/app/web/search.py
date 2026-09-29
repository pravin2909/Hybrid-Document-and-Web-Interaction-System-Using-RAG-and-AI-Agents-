from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from ..config import Settings


@dataclass
class WebResult:
    title: str
    url: str
    content: str


def _fetch_readable(url: str, timeout: float, limit: int = 4000) -> str:
    """Best-effort fetch and strip of a page's main text."""
    if not url.startswith(("http://", "https://")):
        return ""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgenticRAG/1.0)"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.decompose()
        return " ".join(soup.stripped_strings)[:limit]
    except requests.RequestException:
        return ""


class WebSearch:
    """Provider-agnostic web search.

    Selection order when provider == "auto":
        Tavily (if TAVILY_API_KEY) > SearXNG (if SEARXNG_URL) > DuckDuckGo.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.max_results = settings.web_search_results
        self.timeout = settings.http_timeout
        self.provider = self._resolve_provider(settings)

    def _resolve_provider(self, s: Settings) -> str:
        choice = (s.web_search_provider or "auto").lower()
        if choice != "auto":
            return choice
        if s.tavily_api_key:
            return "tavily"
        if s.searxng_url:
            return "searxng"
        return "duckduckgo"

    def search(self, query: str) -> list[WebResult]:
        try:
            if self.provider == "tavily":
                return self._tavily(query)
            if self.provider == "searxng":
                return self._searxng(query)
            return self._duckduckgo(query)
        except Exception:
            # Never let a flaky search provider crash the agent turn.
            if self.provider != "duckduckgo":
                try:
                    return self._duckduckgo(query)
                except Exception:
                    return []
            return []

    # ── providers ───────────────────────────────────────────────────────────
    def _tavily(self, query: str) -> list[WebResult]:
        from tavily import TavilyClient

        client = TavilyClient(api_key=self.settings.tavily_api_key)
        data = client.search(
            query=query,
            max_results=self.max_results,
            search_depth="advanced",
            include_raw_content=True,
        )
        results: list[WebResult] = []
        for item in data.get("results", []):
            results.append(
                WebResult(
                    title=item.get("title", "Result"),
                    url=item.get("url", ""),
                    content=(item.get("raw_content") or item.get("content") or "")[:4000],
                )
            )
        return results

    def _searxng(self, query: str) -> list[WebResult]:
        resp = requests.get(
            self.settings.searxng_url.rstrip("/") + "/search",
            params={"q": query, "format": "json"},
            timeout=self.timeout,
            headers={"User-Agent": "AgenticRAG/1.0"},
        )
        resp.raise_for_status()
        results: list[WebResult] = []
        for item in resp.json().get("results", [])[: self.max_results]:
            url = item.get("url", "")
            snippet = item.get("content", "")
            body = _fetch_readable(url, self.timeout) or snippet
            results.append(WebResult(title=item.get("title", "Result"), url=url, content=body))
        return results

    def _duckduckgo(self, query: str) -> list[WebResult]:
        from ddgs import DDGS

        hits = list(DDGS().text(query, max_results=self.max_results))
        results: list[WebResult] = []
        for hit in hits:
            url = hit.get("href", "")
            snippet = hit.get("body", "")
            body = _fetch_readable(url, self.timeout) or snippet
            results.append(WebResult(title=hit.get("title", "Result"), url=url, content=body))
        return results
