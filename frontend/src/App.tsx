import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteChat as apiDeleteChat,
  getChatMessages,
  getHealth,
  listChats,
  listDocuments,
  streamChat,
} from "./api";
import { Sidebar } from "./components/Sidebar";
import { ChatMessage } from "./components/ChatMessage";
import { Composer } from "./components/Composer";
import { Welcome } from "./components/Welcome";
import { Settings } from "./components/Settings";
import { applyTheme, loadThemeChoice, watchSystemTheme } from "./theme";
import type { ChatSummary, DocumentInfo, Health, Message, ThemeChoice } from "./types";

const uid = () => Math.random().toString(36).slice(2);

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState(() => window.innerWidth <= 860);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeChoice>(loadThemeChoice);
  const scrollRef = useRef<HTMLDivElement>(null);
  const themeRef = useRef(theme);
  themeRef.current = theme;

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await listDocuments());
    } catch {
      /* ignore */
    }
  }, []);

  const refreshChats = useCallback(async () => {
    try {
      setChats(await listChats());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ ok: false }));
    refreshDocuments();
    refreshChats();
  }, [refreshDocuments, refreshChats]);

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => watchSystemTheme(() => themeRef.current), []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const patchLast = useCallback((fn: (m: Message) => Message) => {
    setMessages((prev) => {
      const next = [...prev];
      const i = next.length - 1;
      if (i >= 0 && next[i].role === "assistant") next[i] = fn(next[i]);
      return next;
    });
  }, []);

  const handleSend = useCallback(
    async (text: string) => {
      if (busy) return;
      const userMsg: Message = { id: uid(), role: "user", content: text, citations: [], trace: [] };
      const assistant: Message = {
        id: uid(),
        role: "assistant",
        content: "",
        citations: [],
        trace: [],
        streaming: true,
        activity: "Thinking",
      };
      setMessages((prev) => [...prev, userMsg, assistant]);
      setBusy(true);

      try {
        await streamChat(text, currentChatId, (event) => {
          switch (event.type) {
            case "chat":
              setCurrentChatId(event.chat_id);
              break;
            case "status":
              patchLast((m) => ({ ...m, activity: event.label }));
              break;
            case "token":
              patchLast((m) => ({ ...m, content: m.content + event.text }));
              break;
            case "reset":
              patchLast((m) => ({ ...m, content: "" }));
              break;
            case "tool_call":
              patchLast((m) => ({
                ...m,
                trace: [
                  ...m.trace,
                  {
                    tool: event.name,
                    label: event.name === "search_web" ? "Web search" : "Document search",
                    query: (event.args?.query as string) ?? "",
                  },
                ],
              }));
              break;
            case "tool_result":
              patchLast((m) => {
                const trace = [...m.trace];
                for (let i = trace.length - 1; i >= 0; i--) {
                  if (trace[i].tool === event.name && trace[i].count === undefined) {
                    trace[i] = { ...trace[i], count: event.count, sources: event.sources, error: event.error };
                    break;
                  }
                }
                return { ...m, trace };
              });
              break;
            case "citations":
              patchLast((m) => ({ ...m, citations: event.items }));
              break;
            case "error":
              patchLast((m) => ({ ...m, error: event.message, activity: null }));
              break;
          }
        });
      } catch (err) {
        patchLast((m) => ({ ...m, error: (err as Error).message }));
      } finally {
        patchLast((m) => ({ ...m, streaming: false, activity: null }));
        setBusy(false);
        refreshChats();
      }
    },
    [busy, currentChatId, patchLast, refreshChats]
  );

  const selectChat = useCallback(async (chatId: string) => {
    if (chatId === currentChatId) return;
    try {
      const stored = await getChatMessages(chatId);
      setMessages(
        stored.map((m) => ({
          id: uid(),
          role: m.role,
          content: m.content,
          citations: m.citations ?? [],
          trace: (m.trace ?? []).map((t) => ({
            tool: t.tool,
            label: t.tool === "search_web" ? "Web search" : "Document search",
            query: t.query,
            count: t.count,
          })),
        }))
      );
      setCurrentChatId(chatId);
      if (window.innerWidth <= 860) setCollapsed(true);
    } catch {
      /* ignore */
    }
  }, [currentChatId]);

  const newChat = useCallback(() => {
    if (busy) return;
    setMessages([]);
    setCurrentChatId(null);
  }, [busy]);

  const removeChat = useCallback(
    async (chatId: string) => {
      await apiDeleteChat(chatId);
      if (chatId === currentChatId) newChat();
      refreshChats();
    },
    [currentChatId, newChat, refreshChats]
  );

  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`}>
      <Sidebar
        chats={chats}
        currentChatId={currentChatId}
        documents={documents}
        open={!collapsed}
        onClose={() => setCollapsed(true)}
        onNewChat={newChat}
        onSelectChat={selectChat}
        onDeleteChat={removeChat}
        onDocumentsChanged={refreshDocuments}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="backdrop" data-open={!collapsed} onClick={() => setCollapsed(true)} />

      <main className="main">
        <header className="topbar">
          <button className="icon-btn" onClick={() => setCollapsed((c) => !c)} aria-label="Toggle sidebar">
            <MenuIcon />
          </button>
          <span className="topbar-title">Helios</span>
        </header>

        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {messages.length === 0 ? (
              <Welcome hasDocuments={documents.length > 0} onPick={handleSend} />
            ) : (
              messages.map((m) => <ChatMessage key={m.id} message={m} />)
            )}
          </div>
        </div>

        <Composer busy={busy} onSend={handleSend} />
      </main>

      <Settings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        theme={theme}
        onThemeChange={setTheme}
        health={health}
      />
    </div>
  );
}

function MenuIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

