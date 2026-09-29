# Helios — Agentic RAG Research Assistant

**Helios** is a local-first **agentic RAG** application. Instead of a fixed "retrieve → answer"
pipeline, an LLM agent decides *when* and *where* to look — searching your uploaded
documents, the live web, or both — grades what it finds, and answers with inline
citations. Everything runs against your local **LM Studio** models by default.

```
┌────────────────────┐      SSE stream      ┌──────────────────────────────────┐
│  React + TS (Vite) │  ◀───────────────▶   │  FastAPI backend                 │
│  chat · trace · UI │   /api/chat, docs    │                                  │
└────────────────────┘                      │  ┌────────────────────────────┐  │
                                            │  │ Agent loop (tool-calling)  │  │
                                            │  │  ├─ search_documents ──────┼──┼─▶ Chroma (dense)
                                            │  │  └─ search_web ────────────┼──┼─▶  + BM25 → RRF
                                            │  └────────────────────────────┘  │
                                            │        │ chat + embeddings        │
                                            └────────┼──────────────────────────┘
                                                     ▼
                                            LM Studio (OpenAI-compatible, local)
```

## What makes it "agentic"

The old version had a dropdown where *you* chose "Document" or "Web". Now the
**model** makes that call as a tool-using agent:

1. **Plan** — reads your question and decides which tool(s) it needs.
2. **Act** — calls `search_documents` and/or `search_web`, and may call them
   again with a refined query if the first results are weak.
3. **Ground & cite** — answers only from retrieved evidence + general knowledge,
   citing sources inline as `[1]`, `[2]`, and says so when the answer isn't found.

Every step is streamed to the UI as a visible **agent trace**.

## Key features

- **Tool-calling agent** over LM Studio (works with `gemma-4-e4b`, `qwen2.5`, etc.)
- **Hybrid retrieval** — dense embeddings (Chroma) + BM25 keyword search fused with
  Reciprocal Rank Fusion; far better on names, numbers, and exact terms than pure
  vector search.
- **Persistent, multi-document** knowledge base (survives restarts) — PDF, DOCX,
  TXT/MD, and web-page URLs, with page-number citations.
- **Named chat sessions** — conversations and document metadata are stored in
  **Postgres**; chats are auto-named, listed in the sidebar, and reload with their
  full message history, trace, and citations.
- **Pluggable web search** — auto-selects Tavily → SearXNG → DuckDuckGo, so it works
  with zero config and upgrades cleanly when you add a key.
- **Polished UI** — light / dark / system themes, a settings panel, a collapsible
  sidebar, hover-to-expand knowledge base, live token streaming, collapsible agent
  trace, and source cards.

## Prerequisites

- **Python 3.11+** and **Node 18+**
- **[LM Studio](https://lmstudio.ai)** running its local server with:
  - a chat model that supports tool calling (e.g. `google/gemma-4-e4b` or
    `qwen2.5-coder-7b-instruct-mlx`)
  - an embedding model (e.g. `text-embedding-bge-small-en-v1.5`)
- **PostgreSQL** running locally. Create the database once:
  ```bash
  brew services start postgresql@16   # or your own Postgres
  createdb agentic_rag
  ```
  Tables are created automatically on first backend start.

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit model IDs to match LM Studio
uvicorn app.main:app --reload --port 8000
```

Check it: `curl http://127.0.0.1:8000/api/health` should list your loaded models.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` to the backend.

## Configuration (`backend/.env`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHAT_MODEL` | `google/gemma-4-e4b` | Tool-calling chat model ID in LM Studio |
| `EMBEDDING_MODEL` | `text-embedding-bge-small-en-v1.5` | Embedding model ID |
| `AGENT_MAX_STEPS` | `6` | Max tool-call rounds per question |
| `RETRIEVAL_TOP_K` | `6` | Chunks returned by hybrid search |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1200` / `200` | Chunking (characters) |
| `WEB_SEARCH_PROVIDER` | `auto` | `auto` \| `tavily` \| `searxng` \| `duckduckgo` |
| `TAVILY_API_KEY` | – | Set to use Tavily (best web quality) |
| `SEARXNG_URL` | – | Set to use a self-hosted SearXNG instance |
| `CHROMA_DIR` | `./data/chroma` | Where the vector store persists |
| `DATABASE_URL` | `postgresql://localhost:5432/agentic_rag` | Postgres connection (metadata + chats) |

## Web search providers

Provider is auto-selected: **Tavily** (if `TAVILY_API_KEY`) → **SearXNG**
(if `SEARXNG_URL`) → **DuckDuckGo** (zero-config fallback). Tavily returns clean,
LLM-ready page content and is the recommended upgrade; SearXNG keeps everything
fully local.

## Project layout

```
backend/
  app/
    main.py            FastAPI app + service wiring (lifespan)
    api.py             /api/chat (SSE), documents, chats, health
    config.py          pydantic-settings configuration
    db.py              Postgres storage (documents, chats, messages)
    llm.py             LM Studio client (embeddings + streaming chat)
    agent/
      agent.py         streaming tool-calling agent loop
      tools.py         search_documents / search_web tool specs
      prompts.py       system prompt
    rag/
      ingest.py        PDF/DOCX/TXT/URL loaders + chunking
      store.py         Chroma + BM25 hybrid retrieval (RRF)
    web/search.py      pluggable web search providers
  tests/               unit tests (no LM Studio required)
frontend/
  src/
    App.tsx            state + SSE event handling + chat sessions
    api.ts             fetch-based SSE client + chat/document endpoints
    theme.ts           light / dark / system theme handling
    components/        Sidebar, ChatMessage, AgentTrace, Composer, Welcome, Settings
    index.css          themed UI (light + dark palettes)
```

## Tests

```bash
cd backend && python -m unittest discover -s tests
```

## Roadmap ideas

- Cross-encoder reranker (bge-reranker) after hybrid retrieval
- Retrieval-grading node that forces a web fallback when doc hits are weak
- Per-conversation persistence and multi-session history
- Evaluation harness (RAGAS or a hand-built QA set)
