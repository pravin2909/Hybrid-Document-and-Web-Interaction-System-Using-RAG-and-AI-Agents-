from __future__ import annotations

import json
import uuid
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS documents (
        doc_id     TEXT PRIMARY KEY,
        filename   TEXT NOT NULL,
        kind       TEXT NOT NULL,
        chunks     INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chats (
        id         TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id         BIGSERIAL PRIMARY KEY,
        chat_id    TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
        role       TEXT NOT NULL,
        content    TEXT NOT NULL,
        citations  JSONB NOT NULL DEFAULT '[]',
        trace      JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS messages_chat_idx ON messages(chat_id, id)",
]


class Database:
    """Postgres-backed storage for document metadata and named chat sessions."""

    def __init__(self, dsn: str) -> None:
        self.pool = ConnectionPool(dsn, min_size=1, max_size=5, open=True, kwargs={"autocommit": True})
        self._init_schema()

    def _init_schema(self) -> None:
        with self.pool.connection() as conn:
            for statement in SCHEMA:
                conn.execute(statement)

    def close(self) -> None:
        self.pool.close()

    # ── documents ─────────────────────────────────────────────────────────
    def upsert_document(self, doc_id: str, filename: str, kind: str, chunks: int) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO documents (doc_id, filename, kind, chunks)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE
                    SET filename = EXCLUDED.filename,
                        kind = EXCLUDED.kind,
                        chunks = EXCLUDED.chunks
                """,
                (doc_id, filename, kind, chunks),
            )

    def list_documents(self) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            cur.execute(
                "SELECT doc_id, filename, kind, chunks FROM documents ORDER BY created_at DESC"
            )
            return cur.fetchall()

    def delete_document(self, doc_id: str) -> None:
        with self.pool.connection() as conn:
            conn.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))

    # ── chats ─────────────────────────────────────────────────────────────
    def create_chat(self, name: str = "New chat") -> dict[str, Any]:
        chat_id = uuid.uuid4().hex
        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            cur.execute(
                "INSERT INTO chats (id, name) VALUES (%s, %s) RETURNING id, name, created_at, updated_at",
                (chat_id, name),
            )
            return _serialize(cur.fetchone())

    def list_chats(self) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            cur.execute(
                """
                SELECT c.id, c.name, c.updated_at,
                       (SELECT count(*) FROM messages m WHERE m.chat_id = c.id) AS message_count
                FROM chats c ORDER BY c.updated_at DESC
                """
            )
            return [_serialize(r) for r in cur.fetchall()]

    def chat_exists(self, chat_id: str) -> bool:
        with self.pool.connection() as conn:
            cur = conn.execute("SELECT 1 FROM chats WHERE id = %s", (chat_id,))
            return cur.fetchone() is not None

    def rename_chat(self, chat_id: str, name: str) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                "UPDATE chats SET name = %s, updated_at = now() WHERE id = %s", (name, chat_id)
            )

    def touch_chat(self, chat_id: str) -> None:
        with self.pool.connection() as conn:
            conn.execute("UPDATE chats SET updated_at = now() WHERE id = %s", (chat_id,))

    def delete_chat(self, chat_id: str) -> None:
        with self.pool.connection() as conn:
            conn.execute("DELETE FROM chats WHERE id = %s", (chat_id,))

    def ensure_chat(self, chat_id: str | None) -> str:
        """Return a valid chat id, creating a new chat when needed."""
        if chat_id and self.chat_exists(chat_id):
            return chat_id
        return self.create_chat()["id"]

    # ── messages ──────────────────────────────────────────────────────────
    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        citations: list[dict[str, Any]] | None = None,
        trace: list[dict[str, Any]] | None = None,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (chat_id, role, content, citations, trace)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (chat_id, role, content, Jsonb(citations or []), Jsonb(trace or [])),
            )
            conn.execute("UPDATE chats SET updated_at = now() WHERE id = %s", (chat_id,))

    def list_messages(self, chat_id: str) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            cur.execute(
                "SELECT role, content, citations, trace FROM messages WHERE chat_id = %s ORDER BY id",
                (chat_id,),
            )
            return cur.fetchall()

    def history_for_agent(self, chat_id: str) -> list[dict[str, str]]:
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.list_messages(chat_id)
        ]


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("created_at", "updated_at"):
        if key in out and out[key] is not None:
            out[key] = out[key].isoformat()
    return out
