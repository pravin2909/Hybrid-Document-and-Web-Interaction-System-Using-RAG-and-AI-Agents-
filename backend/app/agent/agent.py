from __future__ import annotations

import json
from typing import Any, Iterator

from ..config import Settings
from ..llm import LMStudioClient
from .prompts import SYSTEM_PROMPT, library_hint
from .tools import Source, Toolbox

Event = dict[str, Any]

_TOOL_LABELS = {
    "search_documents": "Searching your documents",
    "search_web": "Searching the web",
}


class Agent:
    """A streaming tool-calling agent over LM Studio.

    Emits a stream of events describing its reasoning steps, tool calls, and
    the final grounded answer with citations.
    """

    def __init__(self, settings: Settings, llm: LMStudioClient, toolbox: Toolbox) -> None:
        self.settings = settings
        self.llm = llm
        self.toolbox = toolbox

    def run(
        self, question: str, history: list[dict[str, str]], documents: list[dict[str, Any]]
    ) -> Iterator[Event]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": library_hint(documents)},
        ]
        for turn in history[-10:]:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})

        citations: list[dict[str, Any]] = []
        seen: dict[tuple, int] = {}

        try:
            for step in range(self.settings.agent_max_steps):
                yield {"type": "status", "stage": "thinking", "label": "Thinking"}
                content_buf, tool_calls = yield from self._stream_step(messages)

                if not tool_calls:
                    if content_buf.strip():
                        yield {"type": "citations", "items": citations}
                        yield {"type": "done"}
                        return
                    # Model produced neither answer nor tool call — nudge once.
                    messages.append(
                        {
                            "role": "system",
                            "content": "Provide your best final answer now using the evidence above.",
                        }
                    )
                    continue

                # Record the assistant's tool-call turn.
                messages.append(
                    {
                        "role": "assistant",
                        "content": content_buf or "",
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["args"] or "{}"},
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                for tc in tool_calls:
                    yield from self._run_tool(tc, messages, citations, seen)

            # Steps exhausted: force a final answer without tools.
            yield {"type": "status", "stage": "thinking", "label": "Summarizing"}
            content_buf, _ = yield from self._stream_step(messages, allow_tools=False)
            yield {"type": "citations", "items": citations}
            yield {"type": "done"}
        except Exception as exc:  # pragma: no cover - surfaced to the client
            yield {"type": "error", "message": str(exc)}

    # ── one streamed model turn ───────────────────────────────────────────
    def _stream_step(
        self, messages: list[dict[str, Any]], allow_tools: bool = True
    ) -> Iterator[Event]:
        tools = self.toolbox.specs() if allow_tools else None
        stream = self.llm.chat_stream(messages, tools=tools)

        content_buf = ""
        emitted_tokens = False
        acc: dict[int, dict[str, str]] = {}

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                content_buf += delta.content
                emitted_tokens = True
                yield {"type": "token", "text": delta.content}
            for tc in getattr(delta, "tool_calls", None) or []:
                slot = acc.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

        tool_calls = [
            {"id": slot["id"] or f"call_{i}", "name": slot["name"], "args": slot["args"]}
            for i, slot in sorted(acc.items())
            if slot["name"]
        ]

        # If this turn was actually a tool call, discard any interim "thinking" text.
        if tool_calls and emitted_tokens:
            yield {"type": "reset"}
            content_buf = ""

        return content_buf, tool_calls

    # ── execute a single tool call ────────────────────────────────────────
    def _run_tool(
        self,
        tc: dict[str, str],
        messages: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        seen: dict[tuple, int],
    ) -> Iterator[Event]:
        name = tc["name"]
        try:
            args = json.loads(tc["args"] or "{}")
        except json.JSONDecodeError:
            args = {}

        yield {"type": "tool_call", "name": name, "args": args}
        yield {"type": "status", "stage": "tool", "label": _TOOL_LABELS.get(name, name)}

        try:
            sources = self.toolbox.run(name, args)
        except Exception as exc:
            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": f"Tool error: {exc}"}
            )
            yield {"type": "tool_result", "name": name, "count": 0, "sources": [], "error": str(exc)}
            return

        indices = self._register(sources, citations, seen)
        tool_content = self._format_for_model(sources, indices)
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_content})

        yield {
            "type": "tool_result",
            "name": name,
            "count": len(sources),
            "query": args.get("query", ""),
            "sources": [citations[i - 1] for i in indices],
        }

    def _register(
        self, sources: list[Source], citations: list[dict[str, Any]], seen: dict[tuple, int]
    ) -> list[int]:
        indices: list[int] = []
        for src in sources:
            key = (src.type, src.title, src.page, src.url)
            if key in seen:
                indices.append(seen[key])
                continue
            index = len(citations) + 1
            citations.append(src.to_citation(index))
            seen[key] = index
            indices.append(index)
        return indices

    @staticmethod
    def _format_for_model(sources: list[Source], indices: list[int]) -> str:
        if not sources:
            return "No results found."
        blocks = []
        for src, index in zip(sources, indices):
            loc = f" (page {src.page})" if src.page else (f" ({src.url})" if src.url else "")
            blocks.append(f"[{index}] {src.title}{loc}\n{src.text}")
        return "\n\n".join(blocks)
