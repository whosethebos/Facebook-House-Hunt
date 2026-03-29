// frontend/app/search/[id]/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getSearch, extendSearch, type Search, type Listing } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { ListingCard } from "@/components/ListingCard";
import { AgentStatusPanel } from "@/components/AgentStatusPanel";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [search, setSearch] = useState<Search | null>(null);
  const [storedListings, setStoredListings] = useState<Listing[]>([]);
  const [isExtending, setIsExtending] = useState(false);

  const { statusMessages, listings: streamedListings, completeEvent, errorEvent, isConnected, isDone } = useSSE(id);

  // Load existing search data on mount
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
      window.location.reload(); // reconnect SSE
    } catch {
      setIsExtending(false);
    }
  };

  // Merge streamed listings with stored listings (SSE takes priority for active searches)
  const displayListings: Listing[] =
    search?.status === "running" || streamedListings.length > 0
      ? (streamedListings as unknown as Listing[])
      : storedListings;

  if (!search) {
    return (
      <div className="text-slate-400 text-center py-16 animate-pulse">Loading search...</div>
    );
  }

  return (
    <div className="flex gap-6 items-start">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0">
        <AgentStatusPanel
          messages={statusMessages}
          isConnected={isConnected}
          isDone={isDone || search.status !== "running"}
          listingCount={displayListings.length}
          onExtend={isDone || search.status === "completed" ? handleExtend : undefined}
          search={{
            city: search.city,
            areas: search.areas,
            budget_max: search.budget_max,
            property_type: search.property_type,
            furnishing: search.furnishing,
          }}
        />
      </div>

      {/* Main results area */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">
              {displayListings.length > 0
                ? `${displayListings.length} listings found`
                : search.status === "running" ? "Searching..." : "No matching listings"}
            </h1>
            {completeEvent && (
              <p className="text-slate-400 text-sm mt-0.5">
                {completeEvent.data.high_match} strong matches (≥75%)
              </p>
            )}
          </div>
        </div>

        {errorEvent && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 mb-4 text-sm">
            ⚠️ {errorEvent.data.message}
          </div>
        )}

        {displayListings.length === 0 && search.status !== "running" ? (
          <div className="text-center py-16 border border-dashed border-slate-700 rounded-2xl">
            <div className="text-4xl mb-3">😕</div>
            <p className="text-slate-300 font-medium mb-1">No matching listings found</p>
            <p className="text-slate-500 text-sm mb-5">Try extending the search to find more results</p>
            {!isExtending ? (
              <button
                onClick={handleExtend}
                className="bg-sky-500 hover:bg-sky-600 text-white px-5 py-2 rounded-lg font-medium transition-colors text-sm"
              >
                🔍 Extend Search
              </button>
            ) : (
              <p className="text-slate-400 text-sm animate-pulse">Extending search...</p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {displayListings.map((listing) => (
              <ListingCard key={listing.id ?? listing.fb_post_url} listing={listing} />
            ))}
            {(search.status === "running" && !isDone) && (
              <div className="border border-dashed border-slate-700 rounded-xl p-4 text-center">
                <p className="text-slate-500 text-sm animate-pulse">⟳ Searching more groups...</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
