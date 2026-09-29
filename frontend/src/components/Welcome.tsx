import { Logo } from "./Logo";

interface Props {
  hasDocuments: boolean;
  onPick: (text: string) => void;
}

const SUGGESTIONS = [
  { title: "Summarize my documents", detail: "Key points across everything I uploaded", prompt: "Summarize the key points across my uploaded documents." },
  { title: "Find a specific fact", detail: "Names, dates, numbers, decisions", prompt: "What are the most important dates and figures in my documents?" },
  { title: "Search the web", detail: "Current, external information", prompt: "Search the web: what are the latest developments in agentic RAG systems?" },
  { title: "Compare & reason", detail: "Connect ideas and explain", prompt: "Compare the main ideas in my documents and explain how they relate." },
];

export function Welcome({ hasDocuments, onPick }: Props) {
  return (
    <div className="welcome">
      <Logo size={56} className="welcome-mark" />
      <h1>What would you like to research?</h1>
      <p className="welcome-sub">
        {hasDocuments
          ? "Ask a question — the agent retrieves from your documents and the web as needed."
          : "Upload a document from the sidebar, or ask anything and I'll search the web."}
      </p>
      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button className="suggestion" key={s.title} onClick={() => onPick(s.prompt)}>
            <span className="suggestion-title">{s.title}</span>
            <span className="suggestion-detail">{s.detail}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
