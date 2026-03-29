// frontend/app/search/new/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSearch, type ParsedCriteria } from "@/lib/api";
import { SearchInput } from "@/components/SearchInput";

export default function NewSearchPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = async (criteria: ParsedCriteria & { raw_description?: string }) => {
    if (!criteria.city.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const search = await createSearch(criteria);
      router.push(`/search/${search.id}`);
    } catch {
      setError("Failed to start search. Is the backend running?");
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 680, margin: "0 auto" }} className="animate-fade-in">
      {/* Header */}
      <div style={{ marginBottom: 36 }}>
        <p className="label" style={{ marginBottom: 8 }}>New Search</p>
        <h1 style={{
          fontFamily: "var(--font-display, DM Serif Display), Georgia, serif",
          fontSize: 34,
          fontWeight: 400,
          color: "var(--text)",
          letterSpacing: "-0.03em",
          lineHeight: 1.1,
          margin: "0 0 10px",
        }}>
          Find your{" "}
          <span style={{ fontStyle: "italic" }} className="text-gradient">next home</span>
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: 14, margin: 0 }}>
          Describe what you&apos;re looking for — our AI will parse it and search Facebook groups in real time.
        </p>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: 16 }}>
          <div style={{
            width: 48, height: 48, borderRadius: "50%",
            border: "2px solid var(--border)",
            borderTopColor: "var(--accent)",
            animation: "spinSlow 0.85s linear infinite",
          }} />
          <div style={{ textAlign: "center" }}>
            <p style={{ color: "var(--text)", fontWeight: 500, margin: "0 0 4px" }}>Starting your search…</p>
            <p style={{ color: "var(--text-muted)", fontSize: 13, margin: 0 }}>Redirecting to live results</p>
          </div>
        </div>
      ) : (
        <>
          {error && (
            <div style={{
              background: "var(--error-bg)",
              border: "1px solid rgba(248,113,113,0.3)",
              color: "var(--error)",
              borderRadius: "var(--radius-sm)",
              padding: "12px 16px",
              marginBottom: 20,
              fontSize: 13,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              <span style={{ fontSize: 16 }}>⚠</span>
              {error}
            </div>
          )}
          <SearchInput onCriteriaReady={handleStart} />
        </>
      )}
    </div>
  );
}
