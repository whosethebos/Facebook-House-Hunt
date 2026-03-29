// frontend/components/ListingCard.tsx
import type { Listing } from "@/lib/api";

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const color = score >= 75 ? "bg-green-500" : score >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <span className={`${color} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>
      {score}%
    </span>
  );
}

function borderColor(score: number | null): string {
  if (!score) return "border-slate-700";
  if (score >= 75) return "border-l-green-500";
  if (score >= 50) return "border-l-yellow-500";
  return "border-l-red-500";
}

export function ListingCard({ listing }: { listing: Listing }) {
  const relativeDate = listing.posted_at
    ? new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
        Math.round((new Date(listing.posted_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
        "day"
      )
    : null;

  return (
    <div className={`bg-slate-900 border border-slate-800 border-l-4 ${borderColor(listing.match_score)} rounded-xl p-4 flex gap-4 hover:bg-slate-800/60 transition-colors`}>
      {/* Image */}
      {listing.image_urls.length > 0 && (
        <div className="w-24 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-slate-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={listing.image_urls[0]}
            alt="Listing"
            className="w-full h-full object-cover"
            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {listing.extracted_type && (
                <span className="font-semibold text-slate-100 text-sm">{listing.extracted_type}</span>
              )}
              {listing.extracted_area && (
                <span className="text-slate-400 text-sm">in {listing.extracted_area}</span>
              )}
            </div>
            {listing.extracted_rent && (
              <p className="text-green-400 font-semibold text-sm">
                ₹{listing.extracted_rent.toLocaleString("en-IN")}/mo
                {listing.extracted_furnishing && (
                  <span className="text-slate-400 font-normal ml-1.5">• {listing.extracted_furnishing}</span>
                )}
              </p>
            )}
          </div>
          <ScoreBadge score={listing.match_score} />
        </div>

        {listing.summary && (
          <p className="text-slate-400 text-xs leading-relaxed mb-2 line-clamp-2">{listing.summary}</p>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          {listing.group_name && (
            <span className="bg-slate-800 text-slate-400 text-xs px-2 py-0.5 rounded-full">{listing.group_name}</span>
          )}
          {relativeDate && (
            <span className="text-slate-500 text-xs">{relativeDate}</span>
          )}
          <a
            href={listing.fb_post_url}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-sky-500/20 hover:bg-sky-500/30 text-sky-400 text-xs px-2.5 py-0.5 rounded-full transition-colors ml-auto"
          >
            → View on Facebook
          </a>
        </div>
      </div>
    </div>
  );
}
