"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import FlagIcon from "@/src/components/FlagIcon";

interface Position {
  symbol: string;
  name: string | null;
  market: string;
  shares: number;
  avg_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
}

interface Summary {
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
}

export default function MiniPortfolio() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      fetch("/api/real/US/positions").then(r => r.json()),
      fetch("/api/real/KR/positions").then(r => r.json()),
    ]).then(([usRes, krRes]) => {
      const usPositions: Position[] = usRes.status === "fulfilled"
        ? (usRes.value.positions ?? []).map((p: Position) => ({ ...p, market: "US" }))
        : [];
      const krPositions: Position[] = krRes.status === "fulfilled"
        ? (krRes.value.positions ?? []).map((p: Position) => ({ ...p, market: "KR" }))
        : [];
      const all = [...usPositions, ...krPositions];
      setPositions(all);

      const usSummary = usRes.status === "fulfilled" ? usRes.value.summary : null;
      const krSummary = krRes.status === "fulfilled" ? krRes.value.summary : null;
      const totalCost = (usSummary?.total_cost ?? 0) + (krSummary?.total_cost ?? 0);
      const totalValue = (usSummary?.total_value ?? 0) + (krSummary?.total_value ?? 0);
      const totalPnl = totalValue - totalCost;
      setSummary({ total_cost: totalCost, total_value: totalValue, total_pnl: totalPnl, total_pnl_pct: totalCost > 0 ? totalPnl / totalCost : 0 });
      setLoading(false);
    });
  }, []);

  if (loading) return (
    <div className="rounded-lg p-3 animate-pulse" style={{ background: "#1c1c1c", height: 80 }} />
  );

  if (positions.length === 0) return (
    <div className="rounded-lg p-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>내 포트폴리오</p>
        <Link href="/portfolio" className="text-[11px]" style={{ color: "#39ff8f" }}>등록하기 →</Link>
      </div>
      <p className="text-[12px] text-center py-2" style={{ color: "#4a4a4a" }}>보유 종목 없음</p>
    </div>
  );

  const pnlColor = (pct: number | null) => {
    if (pct == null) return "#6e6e6e";
    if (pct <= -0.06) return "#ef4444";
    if (pct < 0) return "#f97316";
    return "#39ff8f";
  };

  const fmt = (n: number) =>
    n >= 0 ? `+${(n * 100).toFixed(1)}%` : `${(n * 100).toFixed(1)}%`;

  return (
    <div className="rounded-lg p-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>내 포트폴리오</p>
        <Link href="/portfolio" className="text-[11px]" style={{ color: "#39ff8f" }}>전체 →</Link>
      </div>

      {/* Total P&L */}
      {summary && (
        <div className="flex items-baseline gap-2 mb-2.5 pb-2.5" style={{ borderBottom: "1px solid #2e2e2e" }}>
          <span
            className="text-lg font-black"
            style={{ color: summary.total_pnl >= 0 ? "#39ff8f" : "#ef4444" }}
          >
            {summary.total_pnl >= 0 ? "+" : ""}
            {summary.total_pnl.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
          </span>
          <span
            className="text-[12px] font-bold"
            style={{ color: summary.total_pnl_pct >= 0 ? "#39ff8f" : "#ef4444" }}
          >
            {fmt(summary.total_pnl_pct)}
          </span>
          <span className="text-[11px] ml-auto" style={{ color: "#4a4a4a" }}>
            {positions.length}종목
          </span>
        </div>
      )}

      {/* Position list */}
      <div className="space-y-1.5">
        {positions.map(pos => {
          const pct = pos.unrealized_pnl_pct;
          const nearStop = pct != null && pct <= -0.06;
          return (
            <div key={`${pos.market}-${pos.symbol}`} className="flex items-center gap-2">
              <FlagIcon market={pos.market as "US" | "KR"} size={12} />
              <span className="text-[12px] font-bold text-white flex-1 min-w-0 truncate">
                {pos.symbol}
              </span>
              {nearStop && (
                <span className="text-[10px] font-bold px-1 rounded" style={{ background: "#ef444422", color: "#ef4444" }}>
                  손절임박
                </span>
              )}
              <span className="text-[12px] font-bold tabular-nums shrink-0" style={{ color: pnlColor(pct) }}>
                {pct != null ? fmt(pct) : "—"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
