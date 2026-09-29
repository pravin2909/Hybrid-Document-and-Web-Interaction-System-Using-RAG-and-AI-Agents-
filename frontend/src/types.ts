export type Role = "user" | "assistant";

export interface Citation {
  index: number;
  type: "document" | "web";
  title: string;
  url?: string | null;
  page?: number | null;
  snippet: string;
}

export interface TraceStep {
  tool: string;
  label: string;
  query?: string;
  count?: number;
  sources?: Citation[];
  error?: string;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  citations: Citation[];
  trace: TraceStep[];
  activity?: string | null;
  streaming?: boolean;
  error?: string | null;
}

export interface DocumentInfo {
  doc_id: string;
  filename: string;
  kind: string;
  chunks: number;
}

export interface Health {
  ok: boolean;
  models?: string[];
  chat_model?: string;
  chat_model_loaded?: boolean;
  embedding_model?: string;
  embedding_model_loaded?: boolean;
  documents?: number;
  web_search_provider?: string;
  error?: string;
}

export interface ChatSummary {
  id: string;
  name: string;
  updated_at: string;
  message_count: number;
}

export interface StoredMessage {
  role: Role;
  content: string;
  citations: Citation[];
  trace: { tool: string; query?: string; count?: number }[];
}

export type ThemeChoice = "system" | "light" | "dark";

export type AgentEvent =
  | { type: "chat"; chat_id: string }
  | { type: "status"; stage: string; label: string }
  | { type: "token"; text: string }
  | { type: "reset" }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | {
      type: "tool_result";
      name: string;
      count: number;
      query?: string;
      sources: Citation[];
      error?: string;
    }
  | { type: "citations"; items: Citation[] }
  | { type: "done" }
  | { type: "error"; message: string };
