import type { Health, ThemeChoice } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  theme: ThemeChoice;
  onThemeChange: (theme: ThemeChoice) => void;
  health: Health | null;
}

const THEMES: { value: ThemeChoice; label: string; icon: string }[] = [
  { value: "system", label: "System", icon: "◐" },
  { value: "light", label: "Light", icon: "☀" },
  { value: "dark", label: "Dark", icon: "☾" },
];

export function Settings({ open, onClose, theme, onThemeChange, health }: Props) {
  if (!open) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Settings</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="settings-group">
          <div className="settings-label">Appearance</div>
          <div className="theme-toggle">
            {THEMES.map((t) => (
              <button
                key={t.value}
                className={`theme-option ${theme === t.value ? "active" : ""}`}
                onClick={() => onThemeChange(t.value)}
              >
                <span className="theme-icon">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="settings-group">
          <div className="settings-label">Runtime</div>
          <div className="settings-info">
            <Row label="Status" value={health?.ok ? "Connected" : "Offline"} ok={health?.ok} />
            <Row label="Chat model" value={health?.chat_model ?? "—"} mono />
            <Row label="Embeddings" value={health?.embedding_model ?? "—"} mono />
            <Row label="Web search" value={health?.web_search_provider ?? "—"} />
            <Row label="Documents indexed" value={String(health?.documents ?? 0)} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono, ok }: { label: string; value: string; mono?: boolean; ok?: boolean }) {
  return (
    <div className="settings-row">
      <span className="settings-row-label">{label}</span>
      <span className={`settings-row-value ${mono ? "mono" : ""} ${ok === undefined ? "" : ok ? "good" : "bad"}`}>
        {value}
      </span>
    </div>
  );
}
