from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

from ..config import Settings
from ..llm import LMStudioClient
from .ingest import Chunk

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class VectorStore:
    """Persistent Chroma collection with hybrid dense + BM25 retrieval.

    Dense vectors are produced by the LM Studio embedding model; a BM25 index
    is maintained in memory over the same chunks and the two rankings are fused
    with Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, settings: Settings, llm: LMStudioClient) -> None:
        self.settings = settings
        self.llm = llm
        self.client = chromadb.PersistentClient(
            path=settings.chroma_dir,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self.collection = self.client.get_or_create_collection(
            name="documents", metadata={"hnsw:space": "cosine"}
        )
        self._bm25: BM25Okapi | None = None
        self._ids: list[str] = []
        self._docs: list[str] = []
        self._metas: list[dict[str, Any]] = []
        self._dirty = True

    # ── writes ────────────────────────────────────────────────────────────
    def add_document(self, doc_id: str, filename: str, kind: str, chunks: list[Chunk]) -> int:
        texts = [c.text for c in chunks]
        embeddings = self.llm.embed(texts).tolist()
        ids = [f"{doc_id}:{c.chunk_index}" for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "kind": kind,
                "page": c.page if c.page is not None else -1,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]
        self.collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        self._dirty = True
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})
        self._dirty = True

    def reset(self) -> None:
        for doc in self.list_documents():
            self.delete_document(doc["doc_id"])

    # ── reads ─────────────────────────────────────────────────────────────
    def count(self) -> int:
        return self.collection.count()

    def list_documents(self) -> list[dict[str, Any]]:
        got = self.collection.get(include=["metadatas"])
        agg: dict[str, dict[str, Any]] = {}
        for meta in got["metadatas"]:
            entry = agg.setdefault(
                meta["doc_id"],
                {
                    "doc_id": meta["doc_id"],
                    "filename": meta["filename"],
                    "kind": meta["kind"],
                    "chunks": 0,
                },
            )
            entry["chunks"] += 1
        return sorted(agg.values(), key=lambda d: d["filename"].lower())

    def _ensure_bm25(self) -> None:
        if not self._dirty and self._bm25 is not None:
            return
        got = self.collection.get(include=["documents", "metadatas"])
        self._ids = got["ids"]
        self._docs = got["documents"]
        self._metas = got["metadatas"]
        self._bm25 = BM25Okapi([_tokenize(d) for d in self._docs]) if self._docs else None
        self._dirty = False

    def hybrid_search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        top_k = top_k or self.settings.retrieval_top_k
        total = self.collection.count()
        if total == 0:
            return []
        pool = min(max(top_k * 4, 12), total)

        # Dense ranking
        query_embedding = self.llm.embed_one(query)
        dense = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=pool,
            include=["documents", "metadatas", "distances"],
        )
        dense_ids = dense["ids"][0]
        table: dict[str, dict[str, Any]] = {}
        for i, did in enumerate(dense_ids):
            table[did] = {
                "id": did,
                "text": dense["documents"][0][i],
                "meta": dense["metadatas"][0][i],
                "score": 1.0 - float(dense["distances"][0][i]),  # cosine similarity
            }

        # Sparse ranking
        self._ensure_bm25()
        sparse_ids: list[str] = []
        if self._bm25 is not None:
            scores = self._bm25.get_scores(_tokenize(query))
            order = np.argsort(scores)[::-1][:pool]
            for i in order:
                if scores[i] <= 0:
                    continue
                did = self._ids[i]
                sparse_ids.append(did)
                if did not in table:
                    table[did] = {
                        "id": did,
                        "text": self._docs[i],
                        "meta": self._metas[i],
                        "score": None,
                    }

        # Reciprocal Rank Fusion
        k = self.settings.rrf_k
        fused: dict[str, float] = defaultdict(float)
        for rank, did in enumerate(dense_ids):
            fused[did] += 1.0 / (k + rank + 1)
        for rank, did in enumerate(sparse_ids):
            fused[did] += 1.0 / (k + rank + 1)

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [table[did] for did, _ in ranked if did in table]
