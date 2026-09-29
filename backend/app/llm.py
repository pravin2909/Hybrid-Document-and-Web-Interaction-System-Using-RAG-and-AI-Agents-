from __future__ import annotations

from typing import Any, Iterator

import numpy as np
from openai import OpenAI

from .config import Settings


class LMStudioClient:
    """Thin wrapper over LM Studio's OpenAI-compatible API.

    Provides normalized embeddings and both streaming and non-streaming
    chat completions with tool-calling support.
    """

    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self.settings = settings
        self.chat_model = settings.chat_model
        self.embedding_model = settings.embedding_model
        self.batch_size = max(1, settings.embedding_batch_size)
        self.client = client or OpenAI(
            base_url=settings.lmstudio_base_url,
            api_key=settings.lmstudio_api_key,
            timeout=settings.lmstudio_timeout,
        )

    # ── embeddings ────────────────────────────────────────────────────────
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalized embeddings, shape (len(texts), dim)."""
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        chunks: list[np.ndarray] = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset : offset + self.batch_size]
            resp = self.client.embeddings.create(model=self.embedding_model, input=batch)
            data = sorted(resp.data, key=lambda item: item.index)
            if len(data) != len(batch):
                raise ValueError("LM Studio returned an unexpected number of embeddings")
            chunks.append(np.asarray([d.embedding for d in data], dtype=np.float32))
        vectors = np.concatenate(chunks, axis=0)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-12)

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0].tolist()

    # ── chat ──────────────────────────────────────────────────────────────
    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> Iterator[Any]:
        """Yield raw streaming chunks from the chat completion API."""
        kwargs: dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": self.settings.agent_temperature if temperature is None else temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def health(self) -> dict[str, Any]:
        """Return the set of model ids the server currently exposes."""
        models = [m.id for m in self.client.models.list().data]
        return {
            "ok": True,
            "models": models,
            "chat_model": self.chat_model,
            "chat_model_loaded": self.chat_model in models,
            "embedding_model": self.embedding_model,
            "embedding_model_loaded": self.embedding_model in models,
        }
