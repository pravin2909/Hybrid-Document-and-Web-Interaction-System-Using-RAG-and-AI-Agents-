import type { AgentEvent, ChatSummary, DocumentInfo, Health, StoredMessage } from "./types";

const API = "/api";

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API}/health`);
  return res.json();
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${API}/documents`);
  if (!res.ok) throw new Error("Failed to load documents");
  return res.json();
}

export async function uploadDocument(file: File): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/documents`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Upload failed");
  }
  return res.json();
}

export async function ingestUrl(url: string): Promise<DocumentInfo> {
  const res = await fetch(`${API}/documents/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Could not fetch URL");
  }
  return res.json();
}

export async function deleteDocument(docId: string): Promise<void> {
  await fetch(`${API}/documents/${docId}`, { method: "DELETE" });
}

export async function listChats(): Promise<ChatSummary[]> {
  const res = await fetch(`${API}/chats`);
  if (!res.ok) throw new Error("Failed to load chats");
  return res.json();
}

export async function getChatMessages(chatId: string): Promise<StoredMessage[]> {
  const res = await fetch(`${API}/chats/${chatId}/messages`);
  if (!res.ok) throw new Error("Failed to load messages");
  return res.json();
}

export async function renameChat(chatId: string, name: string): Promise<void> {
  await fetch(`${API}/chats/${chatId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function deleteChat(chatId: string): Promise<void> {
  await fetch(`${API}/chats/${chatId}`, { method: "DELETE" });
}

/** POST /api/chat and invoke onEvent for each streamed agent event. */
export async function streamChat(
  message: string,
  chatId: string | null,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, chat_id: chatId }),
    signal,
  });
  if (!res.body) throw new Error("No response stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") return;
      try {
        onEvent(JSON.parse(payload) as AgentEvent);
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
