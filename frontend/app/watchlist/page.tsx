"use client";

import { useEffect, useState, useCallback } from "react";

// ── Types ──────────────────────────────────────────────────────────
interface Candidate {
  market: string;
  symbol: string;
  name: string | null;
  market_cap: number | null;
  sector: string | null;
  piotroski: number | null;
  debt_ratio: number | null;
  interest_coverage: number | null;
  cfo_positive_count: number;
  red_flags: string[];
  regime_fit: "growth" | "dividend" | "neutral";
}

interface WatchItem {
  id: number;
  market: string;
  symbol: string;
  name: string | null;
  note: string | null;
  added_at: string;
}

// ── Helpers ─────────────────────────────────────────────────────────
const FMT_CAP_US = (n: number) =>
  n >= 1e12 ? `$${(n / 1e12).toFixed(1)}T`
  : n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B`
  : `$${(n / 1e6).toFixed(0)}M`;

const FMT_CAP_KR = (n: number) =>
  n >= 1e12 ? `${(n / 1e12).toFixed(1)}조`
  : `${(n / 1e8).toFixed(0)}억`;

function formatCap(market: string, cap: number | null) {
  if (!cap) return "-";
  return market === "KR" ? FMT_CAP_KR(cap) : FMT_CAP_US(cap);
}

function PiotroskiBadge({ score }: { score: number | null }) {
  if (score === null) return <span style={{ color: "#4b5563" }}>-</span>;
  const color = score >= 7 ? "#4ade80" : score >= 5 ? "#facc15" : "#f87171";
  return (
    <span
      style={{
        background: color + "20",
        color,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        padding: "1px 6px",
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {score}/9
    </span>
  );
}

function RegimeBadge({ fit }: { fit: string }) {
  const map: Record<string, { label: string; color: string }> = {
    growth:   { label: "성장",   color: "#60a5fa" },
    dividend: { label: "배당",   color: "#4ade80" },
    neutral:  { label: "중립",   color: "#9ca3af" },
  };
  const { label, color } = map[fit] ?? map.neutral;
  return (
    <span
      style={{
        background: color + "20",
        color,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        padding: "1px 6px",
        fontSize: 11,
      }}
    >
      {label}
    </span>
  );
}

// ── Main Page ────────────────────────────────────────────────────────
export default function WatchlistPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [myList, setMyList]         = useState<WatchItem[]>([]);
  const [screened_at, setScreenedAt] = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const [tab, setTab]               = useState<"candidates" | "my">("candidates");
  const [marketFilter, setMarketFilter]     = useState<"ALL" | "US" | "KR">("ALL");
  const [regimeFilter, setRegimeFilter]     = useState<"ALL" | "growth" | "dividend" | "neutral">("ALL");
  const [addedSymbols, setAddedSymbols]     = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cRes, mRes] = await Promise.all([
        fetch("/api/watchlist/candidates"),
        fetch("/api/watchlist/my"),
      ]);
      const cData = await cRes.json();
      const mData: WatchItem[] = await mRes.json();
      setCandidates(cData.candidates ?? []);
      setScreenedAt(cData.screened_at ?? null);
      setMyList(mData);
      setAddedSymbols(new Set(mData.map((w) => `${w.market}:${w.symbol}`)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addToWatchlist = async (c: Candidate) => {
    await fetch("/api/watchlist/my", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ market: c.market, symbol: c.symbol, name: c.name }),
    });
    load();
  };

  const removeFromWatchlist = async (id: number) => {
    await fetch(`/api/watchlist/my/${id}`, { method: "DELETE" });
    load();
  };

  // 필터 적용
  const filtered = candidates.filter((c) => {
    if (marketFilter !== "ALL" && c.market !== marketFilter) return false;
    if (regimeFilter !== "ALL" && c.regime_fit !== regimeFilter) return false;
    return true;
  });

  const statStyle: React.CSSProperties = {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 8,
    padding: "10px 16px",
    textAlign: "center",
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px", color: "#e5e7eb" }}>
      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>워치리스트</h1>
        <p style={{ color: "#6b7280", fontSize: 13, marginTop: 4 }}>
          함정 필터 통과 종목 · Piotroski F-Score 기반 재무 건전성
          {screened_at && (
            <span style={{ marginLeft: 8, color: "#374151" }}>
              (스크리닝: {screened_at.slice(0, 10)})
            </span>
          )}
        </p>
      </div>

      {/* 통계 카드 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "후보 종목", value: candidates.length },
          { label: "내 워치리스트", value: myList.length },
          { label: "성장 후보", value: candidates.filter((c) => c.regime_fit === "growth").length },
          { label: "배당 후보", value: candidates.filter((c) => c.regime_fit === "dividend").length },
        ].map(({ label, value }) => (
          <div key={label} style={statStyle}>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#39ff8f" }}>{value}</div>
            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* 탭 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, borderBottom: "1px solid #222", paddingBottom: 12 }}>
        {(["candidates", "my"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: tab === t ? "#39ff8f20" : "transparent",
              color: tab === t ? "#39ff8f" : "#6b7280",
              border: `1px solid ${tab === t ? "#39ff8f40" : "#374151"}`,
              borderRadius: 6,
              padding: "6px 16px",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            {t === "candidates" ? `스크리닝 후보 (${filtered.length})` : `내 워치리스트 (${myList.length})`}
          </button>
        ))}
      </div>

      {/* ── 스크리닝 후보 탭 ── */}
      {tab === "candidates" && (
        <>
          {/* 필터 */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
            {(["ALL", "US", "KR"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMarketFilter(m)}
                style={{
                  background: marketFilter === m ? "#60a5fa20" : "transparent",
                  color: marketFilter === m ? "#60a5fa" : "#6b7280",
                  border: `1px solid ${marketFilter === m ? "#60a5fa40" : "#374151"}`,
                  borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer",
                }}
              >
                {m === "ALL" ? "전체" : m}
              </button>
            ))}
            <div style={{ width: 1, background: "#374151", margin: "0 4px" }} />
            {(["ALL", "growth", "dividend", "neutral"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setRegimeFilter(r)}
                style={{
                  background: regimeFilter === r ? "#a78bfa20" : "transparent",
                  color: regimeFilter === r ? "#a78bfa" : "#6b7280",
                  border: `1px solid ${regimeFilter === r ? "#a78bfa40" : "#374151"}`,
                  borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer",
                }}
              >
                {r === "ALL" ? "전체" : r === "growth" ? "성장" : r === "dividend" ? "배당" : "중립"}
              </button>
            ))}
          </div>

          {loading ? (
            <div style={{ color: "#6b7280", textAlign: "center", padding: 60 }}>불러오는 중...</div>
          ) : filtered.length === 0 ? (
            <div style={{ color: "#6b7280", textAlign: "center", padding: 60 }}>
              {candidates.length === 0
                ? "스크리닝 데이터 없음. Python 스크리너를 먼저 실행하세요."
                : "필터 조건에 맞는 종목 없음."}
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #222", color: "#6b7280" }}>
                    {["마켓", "티커", "종목명", "시가총액", "섹터", "F-Score", "부채비율", "이자보상", "체제", ""].map((h) => (
                      <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontWeight: 500 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => {
                    const key = `${c.market}:${c.symbol}`;
                    const inList = addedSymbols.has(key);
                    return (
                      <tr
                        key={key}
                        style={{ borderBottom: "1px solid #1a1a1a" }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "#0f0f0f")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <td style={{ padding: "8px 10px" }}>
                          <span style={{ color: c.market === "US" ? "#60a5fa" : "#f87171", fontSize: 11, fontWeight: 600 }}>
                            {c.market}
                          </span>
                        </td>
                        <td style={{ padding: "8px 10px", fontWeight: 600, color: "#e5e7eb" }}>{c.symbol}</td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {c.name ?? "-"}
                        </td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af" }}>{formatCap(c.market, c.market_cap)}</td>
                        <td style={{ padding: "8px 10px", color: "#6b7280", fontSize: 11 }}>{c.sector ?? "-"}</td>
                        <td style={{ padding: "8px 10px" }}><PiotroskiBadge score={c.piotroski} /></td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af" }}>
                          {c.debt_ratio != null ? `${c.debt_ratio}%` : "-"}
                        </td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af" }}>
                          {c.interest_coverage != null ? c.interest_coverage.toFixed(1) + "x" : "-"}
                        </td>
                        <td style={{ padding: "8px 10px" }}><RegimeBadge fit={c.regime_fit} /></td>
                        <td style={{ padding: "8px 10px" }}>
                          <button
                            onClick={() => inList ? null : addToWatchlist(c)}
                            disabled={inList}
                            style={{
                              background: inList ? "#1a1a1a" : "#39ff8f20",
                              color: inList ? "#374151" : "#39ff8f",
                              border: `1px solid ${inList ? "#222" : "#39ff8f40"}`,
                              borderRadius: 4,
                              padding: "3px 10px",
                              fontSize: 11,
                              cursor: inList ? "default" : "pointer",
                            }}
                          >
                            {inList ? "추가됨" : "+ 추가"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── 내 워치리스트 탭 ── */}
      {tab === "my" && (
        <>
          {myList.length === 0 ? (
            <div style={{ color: "#6b7280", textAlign: "center", padding: 60 }}>
              아직 추가한 종목이 없어요.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {myList.map((item) => (
                <div
                  key={item.id}
                  style={{
                    background: "#111",
                    border: "1px solid #222",
                    borderRadius: 8,
                    padding: "12px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                  }}
                >
                  <span style={{ color: item.market === "US" ? "#60a5fa" : "#f87171", fontSize: 11, fontWeight: 600, minWidth: 24 }}>
                    {item.market}
                  </span>
                  <span style={{ fontWeight: 700, fontSize: 15, minWidth: 60 }}>{item.symbol}</span>
                  <span style={{ color: "#9ca3af", flex: 1 }}>{item.name ?? ""}</span>
                  {item.note && <span style={{ color: "#6b7280", fontSize: 12 }}>{item.note}</span>}
                  <span style={{ color: "#374151", fontSize: 11 }}>{item.added_at.slice(0, 10)}</span>
                  <button
                    onClick={() => removeFromWatchlist(item.id)}
                    style={{
                      background: "transparent",
                      color: "#6b7280",
                      border: "1px solid #374151",
                      borderRadius: 4,
                      padding: "2px 8px",
                      fontSize: 11,
                      cursor: "pointer",
                    }}
                  >
                    삭제
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
