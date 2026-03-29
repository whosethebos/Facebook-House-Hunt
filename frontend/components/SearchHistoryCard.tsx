// frontend/components/SearchHistoryCard.tsx
import type { Search } from "@/lib/api";
import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  running: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
};

function scoreColor(score: number | null | undefined): string {
  if (!score) return "text-slate-400";
  if (score >= 75) return "text-green-400";
  if (score >= 50) return "text-yellow-400";
  return "text-red-400";
}

export function SearchHistoryCard({ search }: { search: Search }) {
  const statusClass = STATUS_COLORS[search.status] ?? "bg-slate-700 text-slate-300";
  const date = new Date(search.created_at).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });

  return (
    <Link href={`/search/${search.id}`}>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-sky-500/50 hover:bg-slate-800/60 transition-all cursor-pointer group">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-semibold text-slate-100 group-hover:text-sky-400 transition-colors">
              📍 {search.city}
            </h3>
            {search.areas.length > 0 && (
              <p className="text-sm text-slate-400 mt-0.5">
                {search.areas.join(", ")}
              </p>
            )}
          </div>
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusClass}`}>
            {search.status}
          </span>
        </div>

        <div className="flex items-center gap-4 text-sm text-slate-400 mb-3">
          {search.property_type && <span>🏠 {search.property_type}</span>}
          {search.budget_max && <span>₹ {search.budget_max.toLocaleString("en-IN")}/mo</span>}
          {search.furnishing && <span>✨ {search.furnishing}</span>}
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">{date}</span>
          <div className="flex items-center gap-3">
            {search.listing_count !== undefined && (
              <span className="text-slate-400">{search.listing_count} listings</span>
            )}
            {search.top_score != null && (
              <span className={`font-bold ${scoreColor(search.top_score)}`}>
                Top: {search.top_score}%
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
