from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent.agent import Agent
from .agent.tools import Toolbox
from .api import router
from .config import get_settings
from .db import Database
from .llm import LMStudioClient
from .rag.store import VectorStore
from .web.search import WebSearch


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    llm = LMStudioClient(settings)
    store = VectorStore(settings, llm)
    web = WebSearch(settings)
    toolbox = Toolbox(settings, store, web)
    agent = Agent(settings, llm, toolbox)
    db = Database(settings.database_url)
    # Reconcile any vectors that exist without a metadata row (e.g. first run).
    for doc in store.list_documents():
        db.upsert_document(doc["doc_id"], doc["filename"], doc["kind"], doc["chunks"])
    app.state.services = {
        "settings": settings,
        "llm": llm,
        "store": store,
        "web": web,
        "toolbox": toolbox,
        "agent": agent,
        "db": db,
    }
    try:
        yield
    finally:
        db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Agentic RAG", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
