// frontend/components/SearchInput.tsx
"use client";
import { useState, useEffect, useRef } from "react";
import { parseCriteria, type ParsedCriteria } from "@/lib/api";

interface Props {
  onCriteriaReady: (criteria: ParsedCriteria) => void;
}

const FURNISHING_OPTIONS = ["any", "furnished", "semi-furnished", "unfurnished"];
const TYPE_OPTIONS = ["1BHK", "2BHK", "3BHK", "shared", "studio", "full apartment"];

const INDIAN_CITIES = [
  "Agra", "Ahmedabad", "Aligarh", "Allahabad", "Amritsar", "Aurangabad",
  "Bangalore", "Bareilly", "Bhopal", "Bhubaneswar", "Chandigarh", "Chennai",
  "Coimbatore", "Dehradun", "Delhi", "Dhanbad", "Faridabad", "Ghaziabad",
  "Gurgaon", "Guwahati", "Gwalior", "Haora", "Hubballi-Dharwad", "Hyderabad",
  "Indore", "Jabalpur", "Jaipur", "Jalandhar", "Jodhpur", "Kalyan-Dombivli",
  "Kanpur", "Kochi", "Kolkata", "Kota", "Lucknow", "Ludhiana", "Madurai",
  "Mangalore", "Meerut", "Moradabad", "Mumbai", "Mysore", "Nagpur", "Nashik",
  "Navi Mumbai", "Noida", "Patna", "Pimpri-Chinchwad", "Pune", "Raipur",
  "Rajkot", "Ranchi", "Solapur", "Srinagar", "Surat", "Thane",
  "Thiruvananthapuram", "Tiruchirappalli", "Vadodara", "Varanasi", "Vasai-Virar",
  "Vijayawada", "Visakhapatnam",
];

const fieldLabel: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "var(--text-muted)",
  display: "block",
  marginBottom: 6,
};

const inputStyle: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  color: "var(--text)",
  width: "100%",
  outline: "none",
  fontFamily: "inherit",
  fontSize: 14,
  padding: "9px 12px",
  transition: "border-color 0.2s ease, box-shadow 0.2s ease",
};

export function SearchInput({ onCriteriaReady }: Props) {
  const [description, setDescription] = useState("");
  const [criteria, setCriteria] = useState<ParsedCriteria>({
    city: "", areas: [], budget_max: null,
    property_type: null, furnishing: null, preferences: null,
  });
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [isParsing, setIsParsing] = useState(false);
  const [parsed, setParsed] = useState(false);
  const [areaInput, setAreaInput] = useState("");

  // City autocomplete state
  const [cityInput, setCityInput] = useState("");
  const [citySuggestions, setCitySuggestions] = useState<string[]>([]);
  const [showCitySuggestions, setShowCitySuggestions] = useState(false);
  const cityRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Close city dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (cityRef.current && !cityRef.current.contains(e.target as Node)) {
        setShowCitySuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleCityInput = (val: string) => {
    setCityInput(val);
    setCriteria(c => ({ ...c, city: val }));
    if (val.length >= 1) {
      const filtered = INDIAN_CITIES.filter(c =>
        c.toLowerCase().includes(val.toLowerCase())
      ).slice(0, 8);
      setCitySuggestions(filtered);
      setShowCitySuggestions(filtered.length > 0);
    } else {
      setShowCitySuggestions(false);
    }
  };

  const selectCity = (city: string) => {
    setCityInput(city);
    setCriteria(c => ({ ...c, city }));
    setShowCitySuggestions(false);
  };

  // NL auto-parse
  useEffect(() => {
    if (description.length < 15) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setIsParsing(true);
      try {
        const result = await parseCriteria(description);
        setCriteria(result);
        setCityInput(result.city || "");
        setAreaInput(result.areas.join(", "));
        // Sync property types from parsed result
        if (result.property_type) {
          const types = result.property_type.split(",").map(s => s.trim()).filter(Boolean);
          setSelectedTypes(types.filter(t => TYPE_OPTIONS.includes(t)));
        }
        setParsed(true);
      } catch {
        // user can fill manually
      } finally {
        setIsParsing(false);
      }
    }, 1000);
  }, [description]);

  const toggleType = (type: string) => {
    setSelectedTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  };

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
    const property_type = selectedTypes.length > 0 ? selectedTypes.join(", ") : null;
    onCriteriaReady({
      ...criteria,
      areas: finalAreas,
      property_type,
      raw_description: description,
    } as ParsedCriteria & { raw_description?: string });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* NL prompt box */}
      <div className="card" style={{ padding: "16px 18px" }}>
        <label style={{ ...fieldLabel, marginBottom: 8 }}>
          Describe what you&apos;re looking for
        </label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder={`e.g. "Looking for a furnished 1BHK in Pune near Hinjewadi, budget ₹15,000, no brokerage"`}
          rows={3}
          style={{
            width: "100%",
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--text)",
            fontSize: 14,
            fontFamily: "inherit",
            resize: "none",
            lineHeight: 1.6,
          }}
        />
        <div style={{ marginTop: 10, minHeight: 20 }}>
          {isParsing && (
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span className="dot dot-running" />
              <span style={{ color: "var(--success)", fontSize: 12 }}>Analysing with Ollama…</span>
            </div>
          )}
          {parsed && !isParsing && (
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span className="dot dot-done" />
              <span style={{ color: "var(--accent)", fontSize: 12 }}>Fields auto-filled — edit below if needed</span>
            </div>
          )}
        </div>
      </div>

      {/* Structured fields */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>

        {/* City — searchable autocomplete */}
        <div ref={cityRef} style={{ position: "relative" }}>
          <label style={fieldLabel}>City *</label>
          <input
            className="input-field"
            value={cityInput}
            onChange={e => handleCityInput(e.target.value)}
            onFocus={() => cityInput.length >= 1 && citySuggestions.length > 0 && setShowCitySuggestions(true)}
            placeholder="e.g. Pune"
            autoComplete="off"
            style={inputStyle}
          />
          {showCitySuggestions && (
            <div style={{
              position: "absolute",
              top: "100%",
              left: 0,
              right: 0,
              zIndex: 50,
              marginTop: 4,
              background: "var(--surface-elevated, var(--surface))",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
              overflow: "hidden",
            }}>
              {citySuggestions.map(city => (
                <div
                  key={city}
                  onMouseDown={() => selectCity(city)}
                  style={{
                    padding: "9px 12px",
                    fontSize: 14,
                    color: "var(--text)",
                    cursor: "pointer",
                    transition: "background 0.1s ease",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "var(--surface-hover, rgba(255,255,255,0.06))")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  {city}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Budget */}
        <div>
          <label style={fieldLabel}>Max Budget (₹/mo)</label>
          <input
            className="input-field"
            inputMode="numeric"
            value={criteria.budget_max ?? ""}
            onChange={e => {
              const raw = e.target.value.replace(/\D/g, "");
              setCriteria(c => ({ ...c, budget_max: raw ? parseInt(raw) : null }));
            }}
            placeholder="₹ e.g. 15,000"
            style={inputStyle}
          />
        </div>

        {/* Furnishing */}
        <div>
          <label style={fieldLabel}>Furnishing</label>
          <select
            className="input-field"
            value={criteria.furnishing ?? "any"}
            onChange={e => setCriteria(c => ({ ...c, furnishing: e.target.value === "any" ? null : e.target.value }))}
            style={inputStyle}
          >
            {FURNISHING_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>

        {/* Property type — multi-select chips */}
        <div style={{ gridColumn: "span 3" }}>
          <label style={fieldLabel}>Property Type</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 2 }}>
            {TYPE_OPTIONS.map(type => {
              const active = selectedTypes.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggleType(type)}
                  style={{
                    padding: "6px 14px",
                    fontSize: 13,
                    fontFamily: "inherit",
                    fontWeight: active ? 600 : 400,
                    borderRadius: "var(--radius-sm)",
                    border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                    background: active ? "rgba(var(--accent-rgb, 99,102,241), 0.15)" : "var(--surface)",
                    color: active ? "var(--accent)" : "var(--text-muted)",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {type}
                </button>
              );
            })}
          </div>
          {selectedTypes.length === 0 && (
            <p style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 6, marginBottom: 0 }}>
              Select one or more — leave empty to match any type
            </p>
          )}
        </div>

        {/* Areas */}
        <div style={{ gridColumn: "span 3" }}>
          <label style={fieldLabel}>Areas / Localities</label>
          <div
            className="input-field"
            style={{
              ...inputStyle,
              display: "flex",
              flexWrap: "wrap",
              gap: 5,
              minHeight: 42,
              alignItems: "center",
              padding: "6px 12px",
              cursor: "text",
            }}
            onClick={e => (e.currentTarget.querySelector("input") as HTMLInputElement | null)?.focus()}
          >
            {criteria.areas.map(area => (
              <span key={area} className="chip">
                {area}
                <button className="chip-remove" onClick={() => removeArea(area)}>×</button>
              </span>
            ))}
            <input
              value={areaInput}
              onChange={e => setAreaInput(e.target.value)}
              onKeyDown={handleAddArea}
              placeholder={criteria.areas.length === 0 ? "e.g. Hinjewadi, Baner — press Enter to add" : ""}
              style={{
                background: "transparent",
                border: "none",
                outline: "none",
                color: "var(--text)",
                fontSize: 14,
                fontFamily: "inherit",
                flex: 1,
                minWidth: 120,
              }}
            />
          </div>
        </div>

        {/* Preferences */}
        <div style={{ gridColumn: "span 3" }}>
          <label style={fieldLabel}>Other Preferences</label>
          <input
            className="input-field"
            value={criteria.preferences ?? ""}
            onChange={e => setCriteria(c => ({ ...c, preferences: e.target.value || null }))}
            placeholder="e.g. no brokerage, near metro, female preferred"
            style={inputStyle}
          />
        </div>
      </div>

      {/* Submit */}
      <button
        className="btn-primary"
        onClick={handleStart}
        disabled={!criteria.city.trim()}
        style={{ width: "100%", justifyContent: "center", fontSize: 15, padding: "13px 0", borderRadius: "var(--radius)" }}
      >
        Start Searching Facebook Groups
      </button>
    </div>
  );
}
