// frontend/app/search/[id]/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getSearch, extendSearch, refreshSearch, confirmFbLogin, type Search, type Listing } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { ListingCard } from "@/components/ListingCard";
import { AgentStatusPanel } from "@/components/AgentStatusPanel";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [search, setSearch] = useState<Search | null>(null);
  const [storedListings, setStoredListings] = useState<Listing[]>([]);
  const [isExtending, setIsExtending] = useState(false);

  const { statusMessages, listings: streamedListings, completeEvent, errorEvent, loginRequiredEvent, isConnected, isDone } = useSSE(id);
  const [loginConfirmed, setLoginConfirmed] = useState(false);
  const [loginConfirming, setLoginConfirming] = useState(false);

  useEffect(() => {
    getSearch(id).then(({ search: s, listings: l }) => {
      setSearch(s);
      if (s.status !== "running") {
        setStoredListings(l as Listing[]);
      }
    }).catch(() => router.push("/"));
  }, [id, router]);

  const handleExtend = async () => {
    if (!id) return;
    setIsExtending(true);
    try {
      await extendSearch(id);
      window.location.reload();
    } catch {
      setIsExtending(false);
    }
  };

  const handleLoginConfirm = async () => {
    if (!id || loginConfirming) return;
    setLoginConfirming(true);
    try {
      await confirmFbLogin(id);
      setLoginConfirmed(true);
    } catch {
      setLoginConfirming(false);
    }
  };

  const handleRefresh = async () => {
    if (!id) return;
    try {
      await refreshSearch(id);
      window.location.reload();
    } catch {
      // ignore — user can retry
    }
  };

  const displayListings: Listing[] =
    search?.status === "running" || streamedListings.length > 0
      ? (streamedListings as unknown as Listing[])
      : storedListings;

  if (!search) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "100px 0", gap: 12 }}>
        <div style={{
          width: 32, height: 32, borderRadius: "50%",
          border: "2px solid var(--border)",
          borderTopColor: "var(--accent)",
          animation: "spinSlow 0.85s linear infinite",
        }} />
        <span style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</span>
      </div>
    );
  }

  const isRunning = search.status === "running" && !isDone;
  const headingText = displayListings.length > 0
    ? `${displayListings.length} listing${displayListings.length !== 1 ? "s" : ""} found`
    : isRunning ? "Searching…" : "No listings found";

  return (
    <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }} className="animate-fade-in">
      {/* Sidebar */}
      <div style={{ width: 256, flexShrink: 0 }}>
        <AgentStatusPanel
          messages={statusMessages}
          isConnected={isConnected}
          isDone={isDone || search.status !== "running"}
          listingCount={displayListings.length}
          onExtend={isDone || search.status === "completed" ? handleExtend : undefined}
          onRefresh={isDone || search.status === "completed" ? handleRefresh : undefined}
          hasGroups={(search.group_urls?.length ?? 0) > 0}
          search={{
            city: search.city,
            areas: search.areas,
            budget_max: search.budget_max,
            property_type: search.property_type,
            furnishing: search.furnishing,
          }}
        />
      </div>

      {/* Main content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Results header */}
        <div style={{ marginBottom: 20 }}>
          <h1 style={{
            fontFamily: "var(--font-display, DM Serif Display), Georgia, serif",
            fontSize: 28,
            fontWeight: 400,
            color: "var(--text)",
            letterSpacing: "-0.03em",
            margin: "0 0 4px",
          }}>
            {headingText}
          </h1>
          {completeEvent && (
            <p style={{ color: "var(--text-muted)", fontSize: 13, margin: 0 }}>
              <span style={{ color: "var(--success)" }}>{completeEvent.data.high_match}</span> strong matches (≥ 75% score)
            </p>
          )}
        </div>

        {/* Facebook 2FA banner */}
        {loginRequiredEvent && !loginConfirmed && (
          <div style={{
            background: "linear-gradient(135deg, rgba(24,119,242,0.12), rgba(24,119,242,0.06))",
            border: "1px solid rgba(24,119,242,0.35)",
            borderRadius: "var(--radius)",
            padding: "16px 20px",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}>
            <div style={{ fontSize: 22, flexShrink: 0 }}>🔐</div>
            <div style={{ flex: 1 }}>
              <p style={{ color: "var(--text)", fontWeight: 600, margin: "0 0 2px", fontSize: 14 }}>
                Facebook login required
              </p>
              <p style={{ color: "var(--text-muted)", fontSize: 13, margin: 0 }}>
                A browser window has opened. Complete your login (including any 2FA), then click Continue.
              </p>
            </div>
            <button
              className="btn-primary"
              onClick={handleLoginConfirm}
              disabled={loginConfirming}
              style={{ flexShrink: 0, fontSize: 13, padding: "9px 20px" }}
            >
              {loginConfirming ? "Confirming…" : "I'm logged in — Continue"}
            </button>
          </div>
        )}

        {/* Error banner */}
        {errorEvent && (
          <div style={{
            background: "var(--error-bg)",
            border: "1px solid rgba(248,113,113,0.3)",
            color: "var(--error)",
            borderRadius: "var(--radius-sm)",
            padding: "12px 16px",
            marginBottom: 16,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}>
            <span>⚠</span> {errorEvent.data.message}
          </div>
        )}

        {/* Listings or empty state */}
        {displayListings.length === 0 && !isRunning ? (
          <div className="empty-state" style={{ textAlign: "center", padding: "60px 32px" }}>
            <div style={{ fontSize: 40, marginBottom: 16, opacity: 0.5 }}>🔍</div>
            <p style={{ color: "var(--text)", fontWeight: 500, marginBottom: 6 }}>No matching listings found</p>
            <p style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 24 }}>
              Try extending the search to cover more Facebook groups
            </p>
            {isExtending ? (
              <p style={{ color: "var(--text-muted)", fontSize: 13 }} className="animate-glow-pulse">Extending search…</p>
            ) : (
              <button className="btn-primary" onClick={handleExtend} style={{ fontSize: 13, padding: "9px 20px" }}>
                Extend Search
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {displayListings.map((listing, i) => (
              <ListingCard key={listing.id ?? listing.fb_post_url} listing={listing} index={i} />
            ))}
            {isRunning && (
              <div style={{
                border: "1px dashed rgba(129,140,248,0.2)",
                borderRadius: "var(--radius)",
                padding: "16px",
                textAlign: "center",
              }}>
                <p style={{ color: "var(--text-muted)", fontSize: 13, margin: 0 }} className="animate-glow-pulse">
                  Scanning more groups…
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
