// frontend/components/SearchHistoryCard.tsx
"use client";
import { useState } from "react";
import type { Search } from "@/lib/api";
import Link from "next/link";

function statusBadgeStyle(status: string): { bg: string; color: string; dot: string } {
  switch (status) {
    case "running":   return { bg: "var(--warning-bg)",  color: "var(--warning)",  dot: "var(--warning)" };
    case "completed": return { bg: "var(--success-bg)",  color: "var(--success)",  dot: "var(--success)" };
    case "failed":    return { bg: "var(--error-bg)",    color: "var(--error)",    dot: "var(--error)" };
    default:          return { bg: "rgba(129,140,248,0.1)", color: "var(--accent)", dot: "var(--accent)" };
  }
}

function scoreColor(score: number | null | undefined): string {
  if (!score) return "var(--text-muted)";
  if (score >= 75) return "var(--success)";
  if (score >= 50) return "var(--warning)";
  return "var(--error)";
}

export function SearchHistoryCard({ search, index = 0, onDelete }: { search: Search; index?: number; onDelete?: (id: string) => void }) {
  const { bg, color, dot } = statusBadgeStyle(search.status);
  const [confirming, setConfirming] = useState(false);
  const date = new Date(search.created_at).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });
  const delay = Math.min(index, 5);

  const handleDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirming) { setConfirming(true); return; }
    onDelete?.(search.id);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setConfirming(false);
  };

  return (
    <Link href={`/search/${search.id}`} style={{ textDecoration: "none" }}>
      <article
        className={`card animate-fade-up stagger-${delay}`}
        style={{ padding: "18px 20px", cursor: "pointer", display: "block" }}
      >
        {/* Top row */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12, gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <h3 style={{
              fontFamily: "var(--font-display, DM Serif Display), Georgia, serif",
              fontSize: 17,
              fontWeight: 400,
              color: "var(--text)",
              margin: "0 0 3px",
              letterSpacing: "-0.02em",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}>
              {search.city}
            </h3>
            {search.areas.length > 0 && (
              <p style={{ color: "var(--text-muted)", fontSize: 12, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {search.areas.join(" · ")}
              </p>
            )}
          </div>
          {/* Right side: status + delete */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <span style={{
              background: bg, color, borderRadius: 100,
              fontSize: 11, fontWeight: 600, padding: "3px 10px",
              display: "flex", alignItems: "center", gap: 5,
              whiteSpace: "nowrap",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: dot, display: "inline-block", flexShrink: 0 }} />
              {search.status}
            </span>
            {onDelete && (
              confirming ? (
                <>
                  <button
                    onClick={handleDelete}
                    title="Confirm delete"
                    style={{
                      background: "var(--error-bg)", border: "1px solid rgba(248,113,113,0.4)",
                      color: "var(--error)", borderRadius: 6, padding: "3px 8px",
                      fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                    }}
                  >
                    Delete
                  </button>
                  <button
                    onClick={handleCancelDelete}
                    title="Cancel"
                    style={{
                      background: "transparent", border: "1px solid var(--border)",
                      color: "var(--text-muted)", borderRadius: 6, padding: "3px 8px",
                      fontSize: 11, cursor: "pointer", fontFamily: "inherit",
                    }}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={handleDelete}
                  title="Delete search"
                  style={{
                    background: "transparent", border: "none",
                    color: "var(--text-dim)", cursor: "pointer",
                    padding: "3px 5px", borderRadius: 5, fontSize: 14, lineHeight: 1,
                    transition: "color 0.15s ease",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.color = "var(--error)")}
                  onMouseLeave={e => (e.currentTarget.style.color = "var(--text-dim)")}
                >
                  ✕
                </button>
              )
            )}
          </div>
        </div>

        {/* Tags row */}
        {(search.property_type || search.budget_max || search.furnishing) && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
            {search.property_type && (
              <span style={{
                background: "rgba(129,140,248,0.08)",
                border: "1px solid rgba(129,140,248,0.15)",
                color: "var(--accent)",
                fontSize: 11, fontWeight: 500,
                padding: "2px 9px", borderRadius: 100,
              }}>
                {search.property_type}
              </span>
            )}
            {search.budget_max && (
              <span style={{
                background: "rgba(52,211,153,0.08)",
                border: "1px solid rgba(52,211,153,0.15)",
                color: "var(--success)",
                fontSize: 11, fontWeight: 500,
                padding: "2px 9px", borderRadius: 100,
              }}>
                ₹{search.budget_max.toLocaleString("en-IN")}/mo
              </span>
            )}
            {search.furnishing && (
              <span style={{
                background: "rgba(251,191,36,0.08)",
                border: "1px solid rgba(251,191,36,0.15)",
                color: "var(--warning)",
                fontSize: 11, fontWeight: 500,
                padding: "2px 9px", borderRadius: 100,
              }}>
                {search.furnishing}
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{date}</span>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {search.listing_count !== undefined && (
              <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                {search.listing_count} listing{search.listing_count !== 1 ? "s" : ""}
              </span>
            )}
            {search.top_score != null && (
              <span style={{ color: scoreColor(search.top_score), fontWeight: 700, fontSize: 13 }}>
                {search.top_score}%
              </span>
            )}
          </div>
        </div>
      </article>
    </Link>
  );
}
