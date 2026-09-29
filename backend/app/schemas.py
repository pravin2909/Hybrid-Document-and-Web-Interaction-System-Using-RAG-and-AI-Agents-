from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    chat_id: str | None = None


class RenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class UrlIngestRequest(BaseModel):
    url: str


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    kind: str
    chunks: int


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    kind: str
    chunks: int
