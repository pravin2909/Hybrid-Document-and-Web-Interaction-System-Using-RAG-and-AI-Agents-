from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..rag.store import VectorStore
from ..web.search import WebSearch


@dataclass
class Source:
    """A single retrieved piece of evidence, shared by the model and the UI."""

    type: str  # "document" | "web"
    title: str
    text: str  # full text handed to the model
    snippet: str  # short text shown in the UI
    url: str | None = None
    page: int | None = None

    def to_citation(self, index: int) -> dict[str, Any]:
        return {
            "index": index,
            "type": self.type,
            "title": self.title,
            "url": self.url,
            "page": self.page,
            "snippet": self.snippet,
        }


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Semantic + keyword search over the user's uploaded documents "
                "(PDFs, Word files, notes, saved web pages). Use this for any "
                "question that could be answered by the user's own files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A focused search query, not the whole user sentence.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the live web for current events, facts, or anything not "
                "in the uploaded documents. Returns extracted page content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A concise web search query."}
                },
                "required": ["query"],
            },
        },
    },
]


class Toolbox:
    def __init__(self, settings: Settings, store: VectorStore, web: WebSearch) -> None:
        self.settings = settings
        self.store = store
        self.web = web

    def specs(self) -> list[dict[str, Any]]:
        return TOOL_SPECS

    def run(self, name: str, args: dict[str, Any]) -> list[Source]:
        if name == "search_documents":
            return self._search_documents(args.get("query", ""))
        if name == "search_web":
            return self._search_web(args.get("query", ""))
        raise ValueError(f"Unknown tool: {name}")

    def _search_documents(self, query: str) -> list[Source]:
        hits = self.store.hybrid_search(query)
        sources: list[Source] = []
        for hit in hits:
            meta = hit["meta"]
            page = meta.get("page")
            page = page if isinstance(page, int) and page > 0 else None
            sources.append(
                Source(
                    type="document",
                    title=meta.get("filename", "document"),
                    text=hit["text"],
                    snippet=hit["text"][:280],
                    page=page,
                )
            )
        return sources

    def _search_web(self, query: str) -> list[Source]:
        results = self.web.search(query)
        return [
            Source(
                type="web",
                title=r.title,
                text=r.content,
                snippet=r.content[:280],
                url=r.url,
            )
            for r in results
            if r.content
        ]
