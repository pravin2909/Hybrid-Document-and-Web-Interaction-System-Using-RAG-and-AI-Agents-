import { useState } from "react";
import type { TraceStep } from "../types";

function ToolIcon({ tool }: { tool: string }) {
  if (tool === "search_web") {
    return (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
      </svg>
    );
  }
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 4h11l5 5v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" />
      <path d="M14 4v6h6" />
    </svg>
  );
}

export function AgentTrace({ trace }: { trace: TraceStep[] }) {
  const [open, setOpen] = useState(false);
  if (trace.length === 0) return null;

  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen((o) => !o)}>
        <span className="trace-spark">✳</span>
        Used {trace.length} {trace.length === 1 ? "step" : "steps"}
        <span className={`chev ${open ? "up" : ""}`}>⌄</span>
      </button>
      {open && (
        <div className="trace-steps">
          {trace.map((step, i) => (
            <div className="trace-step" key={i}>
              <span className="trace-icon">
                <ToolIcon tool={step.tool} />
              </span>
              <div className="trace-body">
                <div className="trace-title">
                  {step.label}
                  {step.count !== undefined && (
                    <span className="trace-count">{step.count} results</span>
                  )}
                </div>
                {step.query && <div className="trace-query">“{step.query}”</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
