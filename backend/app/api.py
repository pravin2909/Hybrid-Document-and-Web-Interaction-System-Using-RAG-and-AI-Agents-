from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .rag import ingest
from .schemas import ChatRequest, DocumentInfo, IngestResponse, RenameRequest, UrlIngestRequest

router = APIRouter(prefix="/api")

_EXT_LOADERS = {
    ".pdf": ingest.load_pdf,
    ".docx": ingest.load_docx,
    ".txt": ingest.load_text,
    ".md": ingest.load_text,
}


def _svc(request: Request) -> dict[str, Any]:
    return request.app.state.services


def _title_from(message: str) -> str:
    title = " ".join(message.split())
    return title[:60] + ("…" if len(title) > 60 else "") or "New chat"


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    svc = _svc(request)
    try:
        info = await run_in_threadpool(svc["llm"].health)
    except Exception as exc:
        info = {"ok": False, "error": str(exc)}
    info["documents"] = await run_in_threadpool(svc["store"].count)
    info["web_search_provider"] = svc["web"].provider
    return info


# ── documents ─────────────────────────────────────────────────────────────
@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(request: Request) -> list[dict[str, Any]]:
    return await run_in_threadpool(_svc(request)["db"].list_documents)


@router.post("/documents", response_model=IngestResponse)
async def upload_document(request: Request, file: UploadFile) -> dict[str, Any]:
    settings = get_settings()
    svc = _svc(request)

    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    loader = _EXT_LOADERS.get(ext)
    if loader is None:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use PDF, DOCX, TXT, or MD.")

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit.")

    def _ingest() -> dict[str, Any]:
        doc = loader(data, filename)
        chunks = ingest.chunk_document(doc, settings.chunk_size, settings.chunk_overlap)
        doc_id = uuid.uuid4().hex
        count = svc["store"].add_document(doc_id, doc.title, doc.kind, chunks)
        svc["db"].upsert_document(doc_id, doc.title, doc.kind, count)
        return {"doc_id": doc_id, "filename": doc.title, "kind": doc.kind, "chunks": count}

    try:
        return await run_in_threadpool(_ingest)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/documents/url", response_model=IngestResponse)
async def ingest_url(request: Request, body: UrlIngestRequest) -> dict[str, Any]:
    settings = get_settings()
    svc = _svc(request)

    def _ingest() -> dict[str, Any]:
        doc = ingest.load_url(body.url, settings.http_timeout)
        chunks = ingest.chunk_document(doc, settings.chunk_size, settings.chunk_overlap)
        doc_id = uuid.uuid4().hex
        count = svc["store"].add_document(doc_id, doc.title, doc.kind, chunks)
        svc["db"].upsert_document(doc_id, doc.title, doc.kind, count)
        return {"doc_id": doc_id, "filename": doc.title, "kind": doc.kind, "chunks": count}

    try:
        return await run_in_threadpool(_ingest)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"Could not fetch that URL: {exc}")


@router.delete("/documents/{doc_id}")
async def delete_document(request: Request, doc_id: str) -> dict[str, bool]:
    svc = _svc(request)
    await run_in_threadpool(svc["store"].delete_document, doc_id)
    await run_in_threadpool(svc["db"].delete_document, doc_id)
    return {"ok": True}


# ── chats ─────────────────────────────────────────────────────────────────
@router.get("/chats")
async def list_chats(request: Request) -> list[dict[str, Any]]:
    return await run_in_threadpool(_svc(request)["db"].list_chats)


@router.post("/chats")
async def create_chat(request: Request) -> dict[str, Any]:
    return await run_in_threadpool(_svc(request)["db"].create_chat)


@router.get("/chats/{chat_id}/messages")
async def chat_messages(request: Request, chat_id: str) -> list[dict[str, Any]]:
    return await run_in_threadpool(_svc(request)["db"].list_messages, chat_id)


@router.patch("/chats/{chat_id}")
async def rename_chat(request: Request, chat_id: str, body: RenameRequest) -> dict[str, bool]:
    await run_in_threadpool(_svc(request)["db"].rename_chat, chat_id, body.name)
    return {"ok": True}


@router.delete("/chats/{chat_id}")
async def delete_chat(request: Request, chat_id: str) -> dict[str, bool]:
    await run_in_threadpool(_svc(request)["db"].delete_chat, chat_id)
    return {"ok": True}


# ── chat (agent, streamed) ──────────────────────────────────────────────────
@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    svc = _svc(request)
    db = svc["db"]

    chat_id = await run_in_threadpool(db.ensure_chat, body.chat_id)
    history = await run_in_threadpool(db.history_for_agent, chat_id)
    documents = await run_in_threadpool(svc["store"].list_documents)

    # Name a fresh chat after its first message.
    if not history:
        await run_in_threadpool(db.rename_chat, chat_id, _title_from(body.message))
    await run_in_threadpool(db.add_message, chat_id, "user", body.message)

    def event_stream():
        agent = svc["agent"]
        content = ""
        citations: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        # Tell the client which chat this belongs to (new or existing).
        yield f"data: {json.dumps({'type': 'chat', 'chat_id': chat_id})}\n\n"
        try:
            for event in agent.run(body.message, history, documents):
                etype = event.get("type")
                if etype == "token":
                    content += event["text"]
                elif etype == "reset":
                    content = ""
                elif etype == "citations":
                    citations = event["items"]
                elif etype == "tool_call":
                    trace.append({"tool": event["name"], "query": (event.get("args") or {}).get("query", "")})
                elif etype == "tool_result":
                    for step in reversed(trace):
                        if step["tool"] == event["name"] and "count" not in step:
                            step["count"] = event["count"]
                            break
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # pragma: no cover
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            db.add_message(chat_id, "assistant", content, citations, trace)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
