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
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-100">Recent Searches</h1>
          <p className="text-slate-400 mt-1">Click a search to view its results</p>
        </div>
        <Link
          href="/search/new"
          className="bg-sky-500 hover:bg-sky-600 text-white px-5 py-2.5 rounded-lg font-medium transition-colors"
        >
          + New Search
        </Link>
      </div>

      {loading ? (
        <div className="text-slate-400 text-center py-16">Loading...</div>
      ) : searches.length === 0 ? (
        <div className="text-center py-20 border border-dashed border-slate-700 rounded-2xl">
          <div className="text-5xl mb-4">🏠</div>
          <h2 className="text-xl font-semibold text-slate-300 mb-2">No searches yet</h2>
          <p className="text-slate-500 mb-6">Start your first Facebook house hunt</p>
          <Link
            href="/search/new"
            className="bg-sky-500 hover:bg-sky-600 text-white px-6 py-3 rounded-lg font-medium transition-colors"
          >
            Start Searching
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {searches.map(s => <SearchHistoryCard key={s.id} search={s} />)}
        </div>
      )}
    </div>
  );
}
