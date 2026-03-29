// frontend/components/SearchInput.tsx
"use client";
import { useState, useEffect, useRef } from "react";
import { parseCriteria, type ParsedCriteria } from "@/lib/api";

interface Props {
  onCriteriaReady: (criteria: ParsedCriteria) => void;
}

const FURNISHING_OPTIONS = ["any", "furnished", "semi-furnished", "unfurnished"];
const TYPE_OPTIONS = ["any", "1BHK", "2BHK", "3BHK", "shared", "studio", "full apartment"];

export function SearchInput({ onCriteriaReady }: Props) {
  const [description, setDescription] = useState("");
  const [criteria, setCriteria] = useState<ParsedCriteria>({
    city: "", areas: [], budget_max: null,
    property_type: null, furnishing: null, preferences: null,
  });
  const [isParsing, setIsParsing] = useState(false);
  const [parsed, setParsed] = useState(false);
  const [areaInput, setAreaInput] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (description.length < 15) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setIsParsing(true);
      try {
        const result = await parseCriteria(description);
        setCriteria(result);
        setAreaInput(result.areas.join(", "));
        setParsed(true);
      } catch {
        // ignore, user can fill manually
      } finally {
        setIsParsing(false);
      }
    }, 1000);
  }, [description]);

  const handleAddArea = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const parts = areaInput.split(",").map(s => s.trim()).filter(Boolean);
      setCriteria(c => ({ ...c, areas: [...new Set([...c.areas, ...parts])] }));
      setAreaInput("");
    }
  };

  const removeArea = (area: string) => {
    setCriteria(c => ({ ...c, areas: c.areas.filter(a => a !== area) }));
  };

  const handleStart = () => {
    const finalAreas = areaInput
      ? [...new Set([...criteria.areas, ...areaInput.split(",").map(s => s.trim()).filter(Boolean)])]
      : criteria.areas;
    onCriteriaReady({ ...criteria, areas: finalAreas, raw_description: description } as ParsedCriteria & { raw_description?: string });
  };

  return (
    <div className="space-y-5">
      {/* NL Input */}
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
        <label className="text-xs text-slate-400 uppercase tracking-wider block mb-2">
          Describe what you&apos;re looking for
        </label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder={`e.g. "Looking for a furnished 1BHK in Pune near Hinjewadi, budget ₹15,000, no brokerage"`}
          rows={3}
          className="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm resize-none focus:outline-none"
        />
        {isParsing && (
          <div className="flex items-center gap-2 mt-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-green-400">Analysing with Ollama...</span>
          </div>
        )}
        {parsed && !isParsing && (
          <span className="text-xs text-sky-400 mt-2 block">✨ Fields auto-filled — edit below if needed</span>
        )}
      </div>

      {/* Structured Fields */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-slate-400 block mb-1">City *</label>
          <input
            value={criteria.city}
            onChange={e => setCriteria(c => ({ ...c, city: e.target.value }))}
            placeholder="e.g. Pune"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          />
        </div>
        <div className="col-span-2 md:col-span-1">
          <label className="text-xs text-slate-400 block mb-1">Max Budget (₹/mo)</label>
          <input
            type="number"
            value={criteria.budget_max ?? ""}
            onChange={e => setCriteria(c => ({ ...c, budget_max: e.target.value ? parseInt(e.target.value) : null }))}
            placeholder="e.g. 15000"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1">Property Type</label>
          <select
            value={criteria.property_type ?? "any"}
            onChange={e => setCriteria(c => ({ ...c, property_type: e.target.value === "any" ? null : e.target.value }))}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          >
            {TYPE_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1">Furnishing</label>
          <select
            value={criteria.furnishing ?? "any"}
            onChange={e => setCriteria(c => ({ ...c, furnishing: e.target.value === "any" ? null : e.target.value }))}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          >
            {FURNISHING_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <div className="col-span-2 md:col-span-3">
          <label className="text-xs text-slate-400 block mb-1">Areas / Localities (press Enter or comma to add)</label>
          <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 flex flex-wrap gap-1.5 min-h-[40px]">
            {criteria.areas.map(area => (
              <span key={area} className="bg-sky-500/20 text-sky-300 text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                {area}
                <button onClick={() => removeArea(area)} className="hover:text-red-400">×</button>
              </span>
            ))}
            <input
              value={areaInput}
              onChange={e => setAreaInput(e.target.value)}
              onKeyDown={handleAddArea}
              placeholder={criteria.areas.length === 0 ? "e.g. Hinjewadi, Baner" : ""}
              className="bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none flex-1 min-w-[120px]"
            />
          </div>
        </div>
        <div className="col-span-2 md:col-span-3">
          <label className="text-xs text-slate-400 block mb-1">Other Preferences</label>
          <input
            value={criteria.preferences ?? ""}
            onChange={e => setCriteria(c => ({ ...c, preferences: e.target.value || null }))}
            placeholder="e.g. no brokerage, near metro, female preferred"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          />
        </div>
      </div>

      <button
        onClick={handleStart}
        disabled={!criteria.city.trim()}
        className="w-full bg-sky-500 hover:bg-sky-600 disabled:bg-slate-700 disabled:text-slate-500 text-white font-semibold py-3 rounded-xl transition-colors"
      >
        ▶ Start Searching Facebook Groups
      </button>
    </div>
  );
}
