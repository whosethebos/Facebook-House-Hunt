// frontend/components/AgentStatusPanel.tsx
"use client";

interface Props {
  messages: string[];
  isConnected: boolean;
  isDone: boolean;
  listingCount: number;
  onExtend?: () => void;
  search: {
    city: string;
    areas: string[];
    budget_max: number | null;
    property_type: string | null;
    furnishing: string | null;
  };
}

export function AgentStatusPanel({ messages, isConnected, isDone, listingCount, onExtend, search }: Props) {
  const latestMessage = messages[messages.length - 1] ?? null;

  return (
    <div
      className="card"
      style={{ padding: "18px 16px", display: "flex", flexDirection: "column", gap: 18, position: "sticky", top: 20 }}
    >
      {/* Search criteria */}
      <div>
        <p className="label" style={{ marginBottom: 10 }}>Search Criteria</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {/* City */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14 }}>📍</span>
            <span style={{ fontWeight: 600, color: "var(--text)", fontSize: 14 }}>{search.city}</span>
          </div>
          {/* Areas */}
          {search.areas.length > 0 && (
            <p style={{ color: "var(--text-muted)", fontSize: 12, margin: 0, paddingLeft: 22 }}>
              {search.areas.join(" · ")}
            </p>
          )}
          {/* Tags */}
          <div style={{ paddingLeft: 22, display: "flex", flexWrap: "wrap", gap: 5, marginTop: 2 }}>
            {search.property_type && (
              <span style={{
                background: "rgba(129,140,248,0.08)", border: "1px solid var(--border)",
                color: "var(--accent)", fontSize: 11, fontWeight: 500,
                padding: "2px 8px", borderRadius: 100,
              }}>{search.property_type}</span>
            )}
            {search.budget_max && (
              <span style={{
                background: "var(--success-bg)", border: "1px solid rgba(52,211,153,0.15)",
                color: "var(--success)", fontSize: 11, fontWeight: 500,
                padding: "2px 8px", borderRadius: 100,
              }}>₹{search.budget_max.toLocaleString("en-IN")}/mo</span>
            )}
            {search.furnishing && (
              <span style={{
                background: "var(--warning-bg)", border: "1px solid rgba(251,191,36,0.15)",
                color: "var(--warning)", fontSize: 11, fontWeight: 500,
                padding: "2px 8px", borderRadius: 100,
              }}>{search.furnishing}</span>
            )}
          </div>
        </div>
      </div>

      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: 0 }} />

      {/* Live status */}
      {!isDone && (
        <div style={{
          background: "rgba(0,0,0,0.25)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-sm)",
          padding: "10px 12px",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: latestMessage ? 8 : 0 }}>
            <span
              className={isConnected ? "dot dot-running" : "dot dot-idle"}
            />
            <span style={{ color: "var(--text-sub)", fontSize: 12, fontWeight: 500 }}>
              {isConnected ? "Agent running…" : "Connecting…"}
            </span>
          </div>
          {latestMessage && (
            <p style={{ color: "var(--text-muted)", fontSize: 11, margin: 0, lineHeight: 1.5, fontFamily: "ui-monospace, monospace" }}>
              {latestMessage}
            </p>
          )}
        </div>
      )}

      {isDone && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="dot dot-done" />
          <span style={{ color: "var(--success)", fontSize: 12, fontWeight: 500 }}>Search complete</span>
        </div>
      )}

      {/* Results count */}
      <div>
        <p className="label" style={{ marginBottom: 6 }}>Results</p>
        <p style={{
          fontFamily: "var(--font-display, DM Serif Display), Georgia, serif",
          fontSize: 36, fontWeight: 400, color: "var(--text)",
          letterSpacing: "-0.04em", margin: "0 0 2px",
          lineHeight: 1,
        }}>
          {listingCount}
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: 12, margin: 0 }}>matching listings</p>
      </div>

      {/* Extend button */}
      {isDone && onExtend && (
        <>
          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: 0 }} />
          <button
            onClick={onExtend}
            className="btn-ghost"
            style={{ width: "100%", justifyContent: "center", fontSize: 13, padding: "8px 0" }}
          >
            Extend Search
          </button>
        </>
      )}

      {/* Activity log */}
      {messages.length > 1 && (
        <>
          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: 0 }} />
          <div>
            <p className="label" style={{ marginBottom: 8 }}>Activity Log</p>
            <div className="terminal" style={{ maxHeight: 140 }}>
              {[...messages].reverse().slice(0, 20).map((msg, i) => (
                <span key={i} className="log-line">{msg}</span>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
