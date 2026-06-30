"use client";

import { useEffect, useState, useCallback } from "react";
import { X, Info } from "lucide-react";

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

// ── 지표 설명 ─────────────────────────────────────────────────────────────────
const INDICATOR_INFO = {
  fscore: {
    title: "Piotroski F-Score (0~9)",
    desc: "수익성·레버리지·운영효율 9가지 항목을 각 1점씩 채점한 재무 건전성 점수입니다.",
    levels: [
      { range: "7~9점", color: "#4ade80", label: "우수 — 재무 상태 탄탄" },
      { range: "5~6점", color: "#facc15", label: "보통 — 무난한 수준" },
      { range: "0~4점", color: "#f87171", label: "취약 — 스크리닝 제외" },
    ],
  },
  debt: {
    title: "부채비율 (총부채/자기자본)",
    desc: "기업이 자기자본 대비 얼마나 많은 부채를 쓰는지 나타냅니다. 낮을수록 재무가 안정적입니다. (금융업 제외)",
    levels: [
      { range: "~100%", color: "#4ade80", label: "안정" },
      { range: "100~150%", color: "#facc15", label: "보통" },
      { range: "150~200%", color: "#f97316", label: "주의" },
      { range: "200% 초과", color: "#f87171", label: "스크리닝 제외" },
    ],
  },
  interest: {
    title: "이자보상배율 (EBIT/이자비용)",
    desc: "영업이익으로 이자를 몇 배 낼 수 있는지 나타냅니다. 1배 미만이면 영업이익으로 이자도 못 내는 좀비기업입니다.",
    levels: [
      { range: "5x 이상", color: "#4ade80", label: "안전" },
      { range: "3~5x", color: "#facc15", label: "보통" },
      { range: "1~3x", color: "#f97316", label: "주의" },
      { range: "1x 미만", color: "#f87171", label: "스크리닝 제외" },
    ],
  },
  regime: {
    title: "시장 체제 적합도",
    desc: "현재 시장 흐름(성장장/배당장)에서 이 종목이 어느 전략에 더 어울리는지를 나타냅니다.",
    levels: [
      { range: "성장", color: "#60a5fa", label: "고성장 — 매출/EPS 성장률 높음" },
      { range: "배당", color: "#4ade80", label: "배당 중심 — 배당수익률 2% 이상" },
      { range: "중립", color: "#9ca3af", label: "뚜렷한 특성 없음" },
    ],
  },
};

// ── Helpers ─────────────────────────────────────────────────────────────────
const FMT_CAP_US = (n: number) =>
  n >= 1e12 ? `$${(n / 1e12).toFixed(1)}T` : n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B` : `$${(n / 1e6).toFixed(0)}M`;
const FMT_CAP_KR = (n: number) =>
  n >= 1e12 ? `${(n / 1e12).toFixed(1)}조` : `${(n / 1e8).toFixed(0)}억`;
function formatCap(market: string, cap: number | null) {
  if (!cap) return "-";
  return market === "KR" ? FMT_CAP_KR(cap) : FMT_CAP_US(cap);
}

function PiotroskiBadge({ score }: { score: number | null }) {
  if (score === null) return <span style={{ color: "#4b5563" }}>-</span>;
  const color = score >= 7 ? "#4ade80" : score >= 5 ? "#facc15" : "#f87171";
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, borderRadius: 4, padding: "1px 6px", fontSize: 12, fontWeight: 600 }}>
      {score}/9
    </span>
  );
}
function RegimeBadge({ fit }: { fit: string }) {
  const map: Record<string, { label: string; color: string }> = {
    growth:   { label: "성장", color: "#60a5fa" },
    dividend: { label: "배당", color: "#4ade80" },
    neutral:  { label: "중립", color: "#9ca3af" },
  };
  const { label, color } = map[fit] ?? map.neutral;
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, borderRadius: 4, padding: "1px 6px", fontSize: 11 }}>
      {label}
    </span>
  );
}

// ── 지표 설명 팝업 ────────────────────────────────────────────────────────────
function InfoModal({ info, onClose }: { info: typeof INDICATOR_INFO[keyof typeof INDICATOR_INFO]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.7)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 max-w-sm w-full space-y-3" style={{ background: "#1c1c1c", border: "1px solid #333" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-bold text-white">{info.title}</h3>
          <button onClick={onClose} style={{ color: "#6b7280" }}><X size={15} /></button>
        </div>
        <p className="text-[12px] leading-relaxed" style={{ color: "#9ca3af" }}>{info.desc}</p>
        <div className="space-y-1.5">
          {info.levels.map((l) => (
            <div key={l.range} className="flex items-center gap-2">
              <span className="text-[11px] font-bold w-16 shrink-0" style={{ color: l.color }}>{l.range}</span>
              <span className="text-[11px]" style={{ color: "#6b7280" }}>{l.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 종목 상세 팝업 ────────────────────────────────────────────────────────────
function DetailModal({ c, inList, onAdd, onClose }: {
  c: Candidate; inList: boolean; onAdd: () => void; onClose: () => void;
}) {
  const coverColor = (v: number | null) => {
    if (!v) return "#6b7280";
    return v >= 5 ? "#4ade80" : v >= 3 ? "#facc15" : v >= 1 ? "#f97316" : "#f87171";
  };
  const debtColor = (v: number | null) => {
    if (!v) return "#6b7280";
    return v <= 100 ? "#4ade80" : v <= 150 ? "#facc15" : v <= 200 ? "#f97316" : "#f87171";
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.75)" }} onClick={onClose}>
      <div className="rounded-2xl w-full max-w-md space-y-4" style={{ background: "#1c1c1c", border: "1px solid #333" }} onClick={(e) => e.stopPropagation()}>
        {/* 헤더 */}
        <div className="flex items-start justify-between px-5 pt-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-bold px-2 py-0.5 rounded" style={{ background: c.market === "US" ? "#60a5fa20" : "#f8717120", color: c.market === "US" ? "#60a5fa" : "#f87171" }}>{c.market}</span>
              <RegimeBadge fit={c.regime_fit} />
            </div>
            <h2 className="text-xl font-black text-white">{c.symbol}</h2>
            {c.name && <p className="text-[13px] mt-0.5" style={{ color: "#9ca3af" }}>{c.name}</p>}
            {c.sector && <p className="text-[11px] mt-0.5" style={{ color: "#6b7280" }}>{c.sector} · {formatCap(c.market, c.market_cap)}</p>}
          </div>
          <button onClick={onClose} className="p-1" style={{ color: "#6b7280" }}><X size={16} /></button>
        </div>

        {/* 지표 그리드 */}
        <div className="px-5 grid grid-cols-2 gap-3">
          {/* F-Score */}
          <div className="rounded-xl p-3" style={{ background: "#141414", border: "1px solid #2e2e2e" }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "#4b5563" }}>Piotroski F-Score</p>
            <p className="text-2xl font-black" style={{ color: c.piotroski != null ? (c.piotroski >= 7 ? "#4ade80" : c.piotroski >= 5 ? "#facc15" : "#f87171") : "#4b5563" }}>
              {c.piotroski ?? "-"}<span className="text-sm font-normal" style={{ color: "#4b5563" }}>/9</span>
            </p>
            <p className="text-[10px] mt-1" style={{ color: "#6b7280" }}>
              {c.piotroski != null ? (c.piotroski >= 7 ? "재무 우수" : c.piotroski >= 5 ? "보통 수준" : "취약") : "데이터 없음"}
            </p>
          </div>

          {/* 부채비율 */}
          <div className="rounded-xl p-3" style={{ background: "#141414", border: "1px solid #2e2e2e" }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "#4b5563" }}>부채비율</p>
            <p className="text-2xl font-black" style={{ color: debtColor(c.debt_ratio) }}>
              {c.debt_ratio != null ? `${c.debt_ratio}%` : "-"}
            </p>
            <p className="text-[10px] mt-1" style={{ color: "#6b7280" }}>총부채 / 자기자본</p>
          </div>

          {/* 이자보상배율 */}
          <div className="rounded-xl p-3" style={{ background: "#141414", border: "1px solid #2e2e2e" }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "#4b5563" }}>이자보상배율</p>
            <p className="text-2xl font-black" style={{ color: coverColor(c.interest_coverage) }}>
              {c.interest_coverage != null ? `${c.interest_coverage.toFixed(1)}x` : "-"}
            </p>
            <p className="text-[10px] mt-1" style={{ color: "#6b7280" }}>영업이익 / 이자비용</p>
          </div>

          {/* 영업현금흐름 */}
          <div className="rounded-xl p-3" style={{ background: "#141414", border: "1px solid #2e2e2e" }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "#4b5563" }}>영업현금흐름</p>
            <p className="text-2xl font-black" style={{ color: c.cfo_positive_count >= 2 ? "#4ade80" : c.cfo_positive_count === 1 ? "#facc15" : "#f87171" }}>
              {c.cfo_positive_count}/2
            </p>
            <p className="text-[10px] mt-1" style={{ color: "#6b7280" }}>최근 2년 중 플러스 연도</p>
          </div>
        </div>

        {/* 체제 설명 */}
        <div className="px-5">
          <div className="rounded-xl p-3" style={{ background: "#141414", border: "1px solid #2e2e2e" }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "#4b5563" }}>시장 체제 적합도</p>
            <div className="flex items-center gap-2">
              <RegimeBadge fit={c.regime_fit} />
              <span className="text-[12px]" style={{ color: "#9ca3af" }}>
                {c.regime_fit === "growth" ? "매출/EPS 성장률 높음 — 성장장에 유리" :
                 c.regime_fit === "dividend" ? "배당수익률 2% 이상 — 배당장에 유리" :
                 "뚜렷한 성장·배당 특성 없음"}
              </span>
            </div>
          </div>
        </div>

        {/* 버튼 */}
        <div className="px-5 pb-5">
          <button
            onClick={() => { onAdd(); onClose(); }}
            disabled={inList}
            className="w-full py-2.5 rounded-xl text-[13px] font-bold transition-opacity disabled:opacity-40"
            style={{ background: inList ? "#1c1c1c" : "#39ff8f18", color: inList ? "#4b5563" : "#39ff8f", border: `1px solid ${inList ? "#2e2e2e" : "#39ff8f33"}` }}>
            {inList ? "이미 워치리스트에 추가됨" : "+ 내 워치리스트에 추가"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 컬럼 헤더 (툴팁) ─────────────────────────────────────────────────────────
function ColHeader({ label, infoKey, onInfo }: {
  label: string;
  infoKey?: keyof typeof INDICATOR_INFO;
  onInfo?: (key: keyof typeof INDICATOR_INFO) => void;
}) {
  return (
    <th style={{ padding: "8px 10px", textAlign: "left", fontWeight: 500, whiteSpace: "nowrap" }}>
      <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#6b7280", fontSize: 12 }}>
        {label}
        {infoKey && onInfo && (
          <button onClick={(e) => { e.stopPropagation(); onInfo(infoKey); }} style={{ color: "#374151", lineHeight: 0 }}>
            <Info size={11} />
          </button>
        )}
      </span>
    </th>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function WatchlistPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [myList, setMyList]         = useState<WatchItem[]>([]);
  const [screened_at, setScreenedAt] = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const [tab, setTab]               = useState<"candidates" | "my">("candidates");
  const [marketFilter, setMarketFilter] = useState<"ALL" | "US" | "KR">("ALL");
  const [regimeFilter, setRegimeFilter] = useState<"ALL" | "growth" | "dividend" | "neutral">("ALL");
  const [addedSymbols, setAddedSymbols] = useState<Set<string>>(new Set());
  const [selected, setSelected]     = useState<Candidate | null>(null);
  const [infoKey, setInfoKey]       = useState<keyof typeof INDICATOR_INFO | null>(null);

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

  const filtered = candidates.filter((c) => {
    if (marketFilter !== "ALL" && c.market !== marketFilter) return false;
    if (regimeFilter !== "ALL" && c.regime_fit !== regimeFilter) return false;
    return true;
  });

  const statStyle: React.CSSProperties = {
    background: "#111", border: "1px solid #222", borderRadius: 8,
    padding: "10px 16px", textAlign: "center",
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px", color: "#e5e7eb" }}>
      {/* 팝업들 */}
      {selected && (
        <DetailModal
          c={selected}
          inList={addedSymbols.has(`${selected.market}:${selected.symbol}`)}
          onAdd={() => addToWatchlist(selected)}
          onClose={() => setSelected(null)}
        />
      )}
      {infoKey && (
        <InfoModal info={INDICATOR_INFO[infoKey]} onClose={() => setInfoKey(null)} />
      )}

      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>워치리스트</h1>
        <p style={{ color: "#6b7280", fontSize: 13, marginTop: 4 }}>
          함정 필터 통과 종목 · Piotroski ≥5 · ROE ≥8% · 매출 성장
          {screened_at && (
            <span style={{ marginLeft: 8, color: "#374151" }}>(스크리닝: {screened_at.slice(0, 10)})</span>
          )}
        </p>
      </div>

      {/* 통계 */}
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
          <button key={t} onClick={() => setTab(t)} style={{
            background: tab === t ? "#39ff8f20" : "transparent",
            color: tab === t ? "#39ff8f" : "#6b7280",
            border: `1px solid ${tab === t ? "#39ff8f40" : "#374151"}`,
            borderRadius: 6, padding: "6px 16px", fontSize: 13, cursor: "pointer",
          }}>
            {t === "candidates" ? `스크리닝 후보 (${filtered.length})` : `내 워치리스트 (${myList.length})`}
          </button>
        ))}
      </div>

      {/* ── 스크리닝 후보 탭 ── */}
      {tab === "candidates" && (
        <>
          <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
            {(["ALL", "US", "KR"] as const).map((m) => (
              <button key={m} onClick={() => setMarketFilter(m)} style={{
                background: marketFilter === m ? "#60a5fa20" : "transparent",
                color: marketFilter === m ? "#60a5fa" : "#6b7280",
                border: `1px solid ${marketFilter === m ? "#60a5fa40" : "#374151"}`,
                borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer",
              }}>{m === "ALL" ? "전체" : m}</button>
            ))}
            <div style={{ width: 1, background: "#374151", margin: "0 4px" }} />
            {(["ALL", "growth", "dividend", "neutral"] as const).map((r) => (
              <button key={r} onClick={() => setRegimeFilter(r)} style={{
                background: regimeFilter === r ? "#a78bfa20" : "transparent",
                color: regimeFilter === r ? "#a78bfa" : "#6b7280",
                border: `1px solid ${regimeFilter === r ? "#a78bfa40" : "#374151"}`,
                borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer",
              }}>{r === "ALL" ? "전체" : r === "growth" ? "성장" : r === "dividend" ? "배당" : "중립"}</button>
            ))}
          </div>

          {loading ? (
            <div style={{ color: "#6b7280", textAlign: "center", padding: 60 }}>불러오는 중...</div>
          ) : filtered.length === 0 ? (
            <div style={{ color: "#6b7280", textAlign: "center", padding: 60 }}>
              {candidates.length === 0 ? "스크리닝 데이터 없음." : "필터 조건에 맞는 종목 없음."}
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <p style={{ fontSize: 11, color: "#374151", marginBottom: 8 }}>행 클릭 시 상세 정보 · ⓘ 클릭 시 지표 설명</p>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #222" }}>
                    <ColHeader label="마켓" />
                    <ColHeader label="티커" />
                    <ColHeader label="종목명" />
                    <ColHeader label="시가총액" />
                    <ColHeader label="섹터" />
                    <ColHeader label="F-Score" infoKey="fscore" onInfo={setInfoKey} />
                    <ColHeader label="부채비율" infoKey="debt" onInfo={setInfoKey} />
                    <ColHeader label="이자보상" infoKey="interest" onInfo={setInfoKey} />
                    <ColHeader label="체제" infoKey="regime" onInfo={setInfoKey} />
                    <th style={{ padding: "8px 10px" }} />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => {
                    const key = `${c.market}:${c.symbol}`;
                    const inList = addedSymbols.has(key);
                    return (
                      <tr key={key}
                        onClick={() => setSelected(c)}
                        style={{ borderBottom: "1px solid #1a1a1a", cursor: "pointer" }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "#0f0f0f")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <td style={{ padding: "8px 10px" }}>
                          <span style={{ color: c.market === "US" ? "#60a5fa" : "#f87171", fontSize: 11, fontWeight: 600 }}>{c.market}</span>
                        </td>
                        <td style={{ padding: "8px 10px", fontWeight: 600, color: "#e5e7eb" }}>{c.symbol}</td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name ?? "-"}</td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af" }}>{formatCap(c.market, c.market_cap)}</td>
                        <td style={{ padding: "8px 10px", color: "#6b7280", fontSize: 11 }}>{c.sector ?? "-"}</td>
                        <td style={{ padding: "8px 10px" }}><PiotroskiBadge score={c.piotroski} /></td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af" }}>{c.debt_ratio != null ? `${c.debt_ratio}%` : "-"}</td>
                        <td style={{ padding: "8px 10px", color: "#9ca3af" }}>{c.interest_coverage != null ? c.interest_coverage.toFixed(1) + "x" : "-"}</td>
                        <td style={{ padding: "8px 10px" }}><RegimeBadge fit={c.regime_fit} /></td>
                        <td style={{ padding: "8px 10px" }} onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => !inList && addToWatchlist(c)}
                            disabled={inList}
                            style={{
                              background: inList ? "#1a1a1a" : "#39ff8f20",
                              color: inList ? "#374151" : "#39ff8f",
                              border: `1px solid ${inList ? "#222" : "#39ff8f40"}`,
                              borderRadius: 4, padding: "3px 10px", fontSize: 11,
                              cursor: inList ? "default" : "pointer",
                            }}>
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
        myList.length === 0 ? (
          <div style={{ color: "#6b7280", textAlign: "center", padding: 60 }}>아직 추가한 종목이 없어요.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {myList.map((item) => (
              <div key={item.id} style={{ background: "#111", border: "1px solid #222", borderRadius: 8, padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ color: item.market === "US" ? "#60a5fa" : "#f87171", fontSize: 11, fontWeight: 600, minWidth: 24 }}>{item.market}</span>
                <span style={{ fontWeight: 700, fontSize: 15, minWidth: 60 }}>{item.symbol}</span>
                <span style={{ color: "#9ca3af", flex: 1 }}>{item.name ?? ""}</span>
                {item.note && <span style={{ color: "#6b7280", fontSize: 12 }}>{item.note}</span>}
                <span style={{ color: "#374151", fontSize: 11 }}>{item.added_at.slice(0, 10)}</span>
                <button onClick={() => removeFromWatchlist(item.id)} style={{ background: "transparent", color: "#6b7280", border: "1px solid #374151", borderRadius: 4, padding: "2px 8px", fontSize: 11, cursor: "pointer" }}>삭제</button>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}
