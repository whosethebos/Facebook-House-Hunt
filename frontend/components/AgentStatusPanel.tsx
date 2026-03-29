// frontend/components/AgentStatusPanel.tsx
"use client";

interface Props {
  messages: string[];
  isConnected: boolean;
  isDone: boolean;
  listingCount: number;
  onExtend?: () => void;
  search: {
    city: string;
    areas: string[];
    budget_max: number | null;
    property_type: string | null;
    furnishing: string | null;
  };
}

export function AgentStatusPanel({ messages, isConnected, isDone, listingCount, onExtend, search }: Props) {
  const latestMessage = messages[messages.length - 1] ?? null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4 sticky top-4">
      {/* Search criteria summary */}
      <div>
        <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Search</p>
        <div className="space-y-1 text-sm">
          <div className="flex items-center gap-1.5 text-slate-200">
            <span>📍</span>
            <span className="font-medium">{search.city}</span>
          </div>
          {search.areas.length > 0 && (
            <div className="text-slate-400 text-xs pl-5">{search.areas.join(", ")}</div>
          )}
          {search.property_type && (
            <div className="text-slate-400 text-xs pl-5">🏠 {search.property_type}</div>
          )}
          {search.budget_max && (
            <div className="text-slate-400 text-xs pl-5">₹ {search.budget_max.toLocaleString("en-IN")}/mo max</div>
          )}
          {search.furnishing && (
            <div className="text-slate-400 text-xs pl-5">✨ {search.furnishing}</div>
          )}
        </div>
      </div>

      {/* Live status */}
      {!isDone && (
        <div className="bg-slate-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            {isConnected ? (
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            ) : (
              <div className="w-2 h-2 rounded-full bg-slate-500" />
            )}
            <span className="text-xs font-medium text-slate-300">
              {isConnected ? "Agent running..." : "Connecting..."}
            </span>
          </div>
          {latestMessage && (
            <p className="text-xs text-slate-400 leading-relaxed">{latestMessage}</p>
          )}
        </div>
      )}

      {/* Results summary */}
      <div className="border-t border-slate-800 pt-3">
        <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Results</p>
        <p className="text-2xl font-bold text-slate-100">{listingCount}</p>
        <p className="text-xs text-slate-500">matching listings found</p>
      </div>

      {/* Extend search */}
      {isDone && onExtend && (
        <button
          onClick={onExtend}
          className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm py-2 rounded-lg transition-colors border border-slate-700"
        >
          🔍 Extend Search
        </button>
      )}

      {/* Recent log */}
      {messages.length > 1 && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Log</p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {[...messages].reverse().slice(0, 20).map((msg, i) => (
              <p key={i} className="text-xs text-slate-500 leading-relaxed">{msg}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
