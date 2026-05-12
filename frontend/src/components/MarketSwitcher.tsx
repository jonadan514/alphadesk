"use client";

import { useMarket } from "@/src/contexts/MarketContext";
import US from "country-flag-icons/react/3x2/US";
import KR from "country-flag-icons/react/3x2/KR";

const FLAGS = { US, KR } as const;

export default function MarketSwitcher() {
  const { market, setMarket } = useMarket();

  return (
    <div
      className="flex items-center rounded-lg overflow-hidden text-[13px] font-bold"
      style={{ border: "1px solid var(--border)", background: "var(--bg-inset)" }}
    >
      {([
        { key: "US" as const, label: "미국" },
        { key: "KR" as const, label: "한국" },
      ]).map(({ key, label }) => {
        const Flag = FLAGS[key];
        return (
          <button
            key={key}
            onClick={() => setMarket(key)}
            className="flex items-center gap-1.5 px-3 py-1.5 transition-all"
            style={{
              background: market === key ? "#39ff8f" : "transparent",
              color:      market === key ? "#000" : "var(--text-muted)",
              cursor:     "pointer",
            }}
          >
            <Flag style={{ width: 20, height: "auto", borderRadius: 2 }} />
            <span className="text-[13px] font-bold">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
