import { useRef, useState } from "react";
import { deleteDocument, ingestUrl, uploadDocument } from "../api";
import type { ChatSummary, DocumentInfo } from "../types";
import { Logo } from "./Logo";

function TrashIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18" />
      <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

interface Props {
  chats: ChatSummary[];
  currentChatId: string | null;
  documents: DocumentInfo[];
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelectChat: (id: string) => void;
  onDeleteChat: (id: string) => void;
  onDocumentsChanged: () => void;
  onOpenSettings: () => void;
}

const KIND_ICON: Record<string, string> = { pdf: "PDF", docx: "DOC", text: "TXT", url: "WEB" };

export function Sidebar({
  chats,
  currentChatId,
  documents,
  open,
  onClose,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  onDocumentsChanged,
  onOpenSettings,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [urlValue, setUrlValue] = useState("");
  const [working, setWorking] = useState(false);
  const [kbOpen, setKbOpen] = useState(false);
  const [kbHover, setKbHover] = useState(false);

  const kbExpanded = kbOpen || kbHover;

  const flash = (msg: string, isError = false) => {
    setError(isError ? msg : null);
    setStatus(isError ? null : msg);
    setTimeout(() => {
      setStatus(null);
      setError(null);
    }, 4000);
  };

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setWorking(true);
    for (const file of Array.from(files)) {
      try {
        const doc = await uploadDocument(file);
        flash(`Indexed ${doc.filename} · ${doc.chunks} chunks`);
      } catch (e) {
        flash((e as Error).message, true);
      }
    }
    setWorking(false);
    onDocumentsChanged();
  };

  const onAddUrl = async () => {
    const url = urlValue.trim();
    if (!url) return;
    setWorking(true);
    try {
      const doc = await ingestUrl(url);
      flash(`Indexed ${doc.filename} · ${doc.chunks} chunks`);
      setUrlValue("");
    } catch (e) {
      flash((e as Error).message, true);
    }
    setWorking(false);
    onDocumentsChanged();
  };

  const onDeleteDoc = async (docId: string) => {
    await deleteDocument(docId);
    onDocumentsChanged();
  };

  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand">
        <Logo size={24} className="brand-mark" />
        <span className="brand-name">Helios</span>
        <button className="icon-btn collapse-btn" onClick={onClose} aria-label="Collapse sidebar">
          «
        </button>
      </div>

      <button className="new-chat" onClick={onNewChat}>
        <span>+</span> New chat
      </button>

      <div className="chats">
        <div className="side-heading">Chats</div>
        <div className="chat-list">
          {chats.length === 0 ? (
            <p className="chat-empty">No conversations yet.</p>
          ) : (
            chats.map((c) => (
              <div
                key={c.id}
                className={`chat-item ${c.id === currentChatId ? "active" : ""}`}
                onClick={() => onSelectChat(c.id)}
              >
                <span className="chat-name" title={c.name}>{c.name}</span>
                <button
                  className="chat-del"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteChat(c.id);
                  }}
                  aria-label="Delete chat"
                >
                  <TrashIcon />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      <div
        className={`kb ${kbExpanded ? "expanded" : ""}`}
        onMouseEnter={() => setKbHover(true)}
        onMouseLeave={() => setKbHover(false)}
      >
        <button className="kb-header" onClick={() => setKbOpen((o) => !o)}>
          <span className="side-heading">Knowledge base</span>
          <span className="kb-count">{documents.length}</span>
          <span className={`chev ${kbExpanded ? "up" : ""}`}>⌄</span>
        </button>

        {kbExpanded && (
        <div className="kb-body">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            multiple
            hidden
            onChange={(e) => onFiles(e.target.files)}
          />
          <button className="upload-btn" disabled={working} onClick={() => fileRef.current?.click()}>
            {working ? "Working…" : "Upload document"}
          </button>
          <div className="url-row">
            <input
              className="url-input"
              placeholder="Add a URL…"
              value={urlValue}
              onChange={(e) => setUrlValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onAddUrl()}
            />
            <button className="url-add" disabled={working || !urlValue.trim()} onClick={onAddUrl}>
              Add
            </button>
          </div>
          {status && <div className="flash ok">{status}</div>}
          {error && <div className="flash err">{error}</div>}

          <div className="doc-list">
            {documents.length === 0 ? (
              <p className="doc-empty">No documents yet.</p>
            ) : (
              documents.map((doc) => (
                <div className="doc-item" key={doc.doc_id}>
                  <span className="doc-kind">{KIND_ICON[doc.kind] ?? "DOC"}</span>
                  <div className="doc-meta">
                    <span className="doc-name" title={doc.filename}>{doc.filename}</span>
                    <span className="doc-sub">{doc.chunks} chunks</span>
                  </div>
                  <button className="doc-del" onClick={() => onDeleteDoc(doc.doc_id)} aria-label="Remove">
                    <TrashIcon />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
        )}
      </div>

      <button className="profile" onClick={onOpenSettings}>
        <span className="avatar-sm">P</span>
        <div className="profile-text">
          <span className="profile-name">Local</span>
          <span className="profile-sub">Settings</span>
        </div>
        <span className="profile-gear">⚙</span>
      </button>
    </aside>
  );
}
