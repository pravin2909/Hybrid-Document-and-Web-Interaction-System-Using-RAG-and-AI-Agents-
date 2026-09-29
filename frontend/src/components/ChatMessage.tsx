import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation, Message } from "../types";
import { AgentTrace } from "./AgentTrace";
import { Logo } from "./Logo";

function Sources({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="sources">
      <div className="sources-title">Sources</div>
      <div className="sources-grid">
        {citations.map((c) => {
          const body = (
            <>
              <span className="src-index">{c.index}</span>
              <div className="src-meta">
                <span className="src-title">{c.title}</span>
                <span className="src-sub">
                  {c.type === "web" ? hostOf(c.url) : c.page ? `page ${c.page}` : "document"}
                </span>
              </div>
            </>
          );
          return c.url ? (
            <a className="src-card" key={c.index} href={c.url} target="_blank" rel="noreferrer">
              {body}
            </a>
          ) : (
            <div className="src-card" key={c.index}>
              {body}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function hostOf(url?: string | null) {
  if (!url) return "web";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "web";
  }
}

export function ChatMessage({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="msg user">
        <div className="bubble user-bubble">{message.content}</div>
      </div>
    );
  }

  const showThinking = message.streaming && !message.content;

  return (
    <div className="msg assistant">
      <div className="avatar"><Logo size={20} /></div>
      <div className="assistant-body">
        <AgentTrace trace={message.trace} />

        {showThinking && (
          <div className="activity">
            <span className="dots"><i /><i /><i /></span>
            {message.activity ?? "Thinking"}
          </div>
        )}

        {message.content && (
          <div className="prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            {message.streaming && <span className="cursor" />}
          </div>
        )}

        {message.error && <div className="msg-error">{message.error}</div>}

        {!message.streaming && <Sources citations={message.citations} />}
      </div>
    </div>
  );
}
