// frontend/app/page.tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { listSearches, type Search } from "@/lib/api";
import { SearchHistoryCard } from "@/components/SearchHistoryCard";

export default function Dashboard() {
  const [searches, setSearches] = useState<Search[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSearches()
      .then(setSearches)
      .catch(() => setSearches([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 36 }}>
        <div>
          <p className="label" style={{ marginBottom: 8 }}>Dashboard</p>
          <h1 style={{
            fontFamily: "var(--font-display, DM Serif Display), Georgia, serif",
            fontSize: 36,
            fontWeight: 400,
            color: "var(--text)",
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
            margin: 0,
          }}>
            Recent{" "}
            <span style={{ fontStyle: "italic" }} className="text-gradient">Searches</span>
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: 14, marginTop: 6, marginBottom: 0 }}>
            Click a search to view its listings
          </p>
        </div>
        <Link href="/search/new" style={{ textDecoration: "none" }}>
          <button className="btn-primary" style={{ fontSize: 14, padding: "10px 20px" }}>
            <span style={{ fontSize: 18, lineHeight: 1 }}>+</span>
            New Search
          </button>
        </Link>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: 12 }}>
          <div style={{
            width: 32, height: 32,
            borderRadius: "50%",
            border: "2px solid var(--border)",
            borderTopColor: "var(--accent)",
            animation: "spinSlow 0.8s linear infinite",
          }} />
          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading searches…</span>
        </div>
      ) : searches.length === 0 ? (
        <div className="empty-state animate-fade-up" style={{ textAlign: "center", padding: "80px 40px" }}>
          <div style={{
            width: 64, height: 64, borderRadius: 18,
            background: "linear-gradient(135deg, var(--accent), var(--accent-2))",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 28, margin: "0 auto 20px", opacity: 0.85,
            boxShadow: "0 8px 32px var(--accent-glow)",
          }}>
            ⌂
          </div>
          <h2 style={{ fontFamily: "var(--font-display, DM Serif Display), Georgia, serif", fontSize: 24, fontWeight: 400, color: "var(--text)", marginBottom: 8, letterSpacing: "-0.02em" }}>
            No searches yet
          </h2>
          <p style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 28 }}>
            Start your first Facebook house hunt — describe what you&apos;re looking for
          </p>
          <Link href="/search/new" style={{ textDecoration: "none" }}>
            <button className="btn-primary" style={{ fontSize: 14, padding: "11px 24px" }}>
              Start Searching
            </button>
          </Link>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14 }}>
          {searches.map((s, i) => (
            <SearchHistoryCard key={s.id} search={s} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
