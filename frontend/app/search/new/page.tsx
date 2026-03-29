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
    } catch (e) {
      setError("Failed to start search. Is the backend running?");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-100 mb-2">New House Hunt</h1>
        <p className="text-slate-400">
          Describe what you&apos;re looking for and we&apos;ll search Facebook groups for you.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-4 animate-pulse">🔍</div>
          <p className="text-slate-300 font-medium">Starting your search...</p>
          <p className="text-slate-500 text-sm mt-1">Redirecting to results</p>
        </div>
      ) : (
        <>
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 mb-5 text-sm">
              {error}
            </div>
          )}
          <SearchInput onCriteriaReady={handleStart} />
        </>
      )}
    </div>
  );
}
