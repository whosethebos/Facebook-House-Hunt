// frontend/components/ListingCard.tsx
import type { Listing } from "@/lib/api";

function ScoreRing({ score }: { score: number | null }) {
  if (score === null) return null;
  const color = score >= 75 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--error)";
  const bg = `conic-gradient(${color} ${score}%, rgba(255,255,255,0.05) ${score}%)`;
  return (
    <div className="score-ring" style={{ background: bg }}>
      <div className="score-ring-inner" style={{ color }}>
        {score}%
      </div>
    </div>
  );
}

export function ListingCard({ listing, index = 0 }: { listing: Listing; index?: number }) {
  const relativeDate = listing.posted_at
    ? new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
        Math.round((new Date(listing.posted_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
        "day"
      )
    : null;

  const accentColor =
    listing.match_score && listing.match_score >= 75 ? "var(--success)" :
    listing.match_score && listing.match_score >= 50 ? "var(--warning)" :
    listing.match_score ? "var(--error)" : "var(--border)";

  const delay = Math.min(index, 5);

  return (
    <article
      className={`card animate-fade-up stagger-${delay}`}
      style={{
        padding: "14px 16px",
        display: "flex",
        gap: 14,
        alignItems: "flex-start",
        borderLeft: `3px solid ${accentColor}`,
        borderRadius: "var(--radius)",
      }}
    >
      {/* Thumbnail */}
      {listing.image_urls.length > 0 && (
        <div style={{
          width: 88, height: 72,
          flexShrink: 0,
          borderRadius: 10,
          overflow: "hidden",
          background: "var(--surface)",
        }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={listing.image_urls[0]}
            alt="Listing photo"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        </div>
      )}

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Title row */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 4 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {listing.extracted_type && (
                <span style={{ fontWeight: 600, color: "var(--text)", fontSize: 14 }}>
                  {listing.extracted_type}
                </span>
              )}
              {listing.extracted_area && (
                <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
                  in {listing.extracted_area}
                </span>
              )}
            </div>
            {listing.extracted_rent && (
              <p style={{ margin: "2px 0 0", fontSize: 14, fontWeight: 600, color: "var(--success)" }}>
                ₹{listing.extracted_rent.toLocaleString("en-IN")}/mo
                {listing.extracted_furnishing && (
                  <span style={{ color: "var(--text-muted)", fontWeight: 400, marginLeft: 6, fontSize: 12 }}>
                    · {listing.extracted_furnishing}
                  </span>
                )}
              </p>
            )}
          </div>
          <ScoreRing score={listing.match_score} />
        </div>

        {/* Summary */}
        {listing.summary && (
          <p style={{
            color: "var(--text-muted)",
            fontSize: 12,
            lineHeight: 1.6,
            margin: "6px 0 8px",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}>
            {listing.summary}
          </p>
        )}

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
          {listing.group_name && (
            <span style={{
              background: "rgba(129,140,248,0.07)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: 11, fontWeight: 500,
              padding: "2px 8px", borderRadius: 100,
            }}>
              {listing.group_name}
            </span>
          )}
          {relativeDate && (
            <span style={{ color: "var(--text-dim)", fontSize: 11 }}>{relativeDate}</span>
          )}
          <a
            href={listing.fb_post_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              marginLeft: "auto",
              background: "rgba(129,140,248,0.1)",
              border: "1px solid rgba(129,140,248,0.2)",
              color: "var(--accent)",
              fontSize: 11, fontWeight: 500,
              padding: "3px 10px", borderRadius: 100,
              textDecoration: "none",
              transition: "background 0.15s, border-color 0.15s",
              whiteSpace: "nowrap",
            }}
          >
            View on Facebook →
          </a>
        </div>
      </div>
    </article>
  );
}
