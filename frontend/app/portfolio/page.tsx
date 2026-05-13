"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useMarket } from "@/src/contexts/MarketContext";
import { AlertTriangle, DollarSign, RefreshCw, Trash2, Plus, Search } from "lucide-react";
import FlagIcon from "@/src/components/FlagIcon";

type Tab = "positions" | "candidates" | "trades";
type Mode = "real" | "paper";

function pct(v: number, digits = 2) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;
}
function krw(v: number) {
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}
function usd(v: number) {
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function fmt(v: number, market: string) {
  return market === "KR" ? krw(v) : usd(v);
}

// ── Candidate Detail Modal ─────────────────────────────────────────────────────
function CandidateDetailModal({ candidate, market, onBuy, onClose }: {
  candidate: any;
  market: string;
  onBuy: () => void;
  onClose: () => void;
}) {
  const isKR = market === "KR";
  const accentColor = candidate.action === "BUY" ? "#39ff8f" : "#facc15";

  const factors = [
    { label: "기술 (Technical)",       val: candidate.technical },
    { label: "펀더멘털 (Fundamental)", val: candidate.fundamental },
    ...(!isKR ? [{ label: "애널리스트 (Analyst)", val: candidate.analyst }] : []),
    { label: isKR ? "RS vs KOSPI" : "RS vs SPY", val: candidate.relative_strength != null
        ? candidate.relative_strength * (Math.abs(candidate.relative_strength) < 2 ? 100 : 1) : null },
    { label: "거래량 (Volume)",        val: candidate.volume },
    ...(!isKR ? [{ label: "기관 (Institutional)", val: candidate.institutional }] : []),
  ].filter((f) => f.val != null);

  const upside = candidate.price && candidate.target_price
    ? (candidate.target_price - candidate.price) / candidate.price
    : null;

  const catalysts: string[] = Array.isArray(candidate.catalysts)
    ? candidate.catalysts
    : typeof candidate.catalysts === "string" ? [candidate.catalysts] : [];
  const bearCases: string[] = Array.isArray(candidate.bear_cases)
    ? candidate.bear_cases
    : typeof candidate.bear_cases === "string" ? [candidate.bear_cases] : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.8)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl overflow-hidden"
        style={{ background: "#1c1c1c", border: `1.5px solid ${accentColor}44`, maxHeight: "85vh", overflowY: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-4" style={{ borderBottom: "1px solid #2e2e2e" }}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[12px] font-black px-2 py-0.5 rounded"
                  style={{ background: `${accentColor}20`, color: accentColor }}>{candidate.action}</span>
                {candidate.grade && (
                  <span className="text-[12px] font-black px-2 py-0.5 rounded"
                    style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
                    Grade {candidate.grade}
                  </span>
                )}
                {candidate.sector && (
                  <span className="text-[12px]" style={{ color: "#6e6e6e" }}>{candidate.sector}</span>
                )}
              </div>
              <h2 className="text-2xl font-black text-white">{candidate.symbol}</h2>
              {candidate.name && candidate.name !== candidate.symbol && (
                <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>{candidate.name}</p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-2xl font-black" style={{ color: accentColor }}>
                  {candidate.composite_score?.toFixed(1) ?? "—"}
                </p>
                <p className="text-[12px]" style={{ color: "#6e6e6e" }}>종합 점수</p>
              </div>
              <button onClick={onClose} className="text-lg font-bold" style={{ color: "#6e6e6e" }}>✕</button>
            </div>
          </div>
        </div>

        <div className="px-5 py-4 space-y-3">
          {/* Price cards */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl p-3" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
              <p className="text-[12px] mb-1" style={{ color: "#6e6e6e" }}>현재가</p>
              <p className="text-xl font-black text-white">
                {candidate.price != null ? fmt(candidate.price, market) : "—"}
              </p>
            </div>
            {candidate.target_price != null && (
              <div className="rounded-xl p-3" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
                <p className="text-[12px] mb-1" style={{ color: "#6e6e6e" }}>목표가</p>
                <p className="text-xl font-black text-white">{fmt(candidate.target_price, market)}</p>
                {upside != null && (
                  <p className="text-[12px] mt-0.5" style={{ color: upside >= 0 ? "#39ff8f" : "#ef4444" }}>
                    {upside >= 0 ? "+" : ""}{(upside * 100).toFixed(1)}% 상승여력
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Lynch/O'Neil indicators */}
          {(candidate.peg_ratio != null || candidate.eps_growth != null || candidate.price_vs_52w_high != null) && (
            <div className="grid grid-cols-3 gap-2">
              {candidate.peg_ratio != null && (() => {
                const threshold = isKR ? 0.7 : 1.0;
                const ok = candidate.peg_ratio < threshold;
                return (
                  <div className="rounded-lg px-2.5 py-2 text-center" style={{ background: "#111111", border: `1px solid ${ok ? "#39ff8f33" : "#1e1e1e"}` }}>
                    <p className="text-[12px] uppercase tracking-widest font-bold mb-0.5" style={{ color: "#6e6e6e" }}>PEG</p>
                    <p className="text-sm font-black" style={{ color: ok ? "#39ff8f" : "#f97316" }}>{candidate.peg_ratio.toFixed(2)}</p>
                    <p className="text-[12px]" style={{ color: ok ? "#39ff8f" : "#6b7280" }}>Lynch {ok ? "✓" : ""}</p>
                  </div>
                );
              })()}
              {candidate.eps_growth != null && (() => {
                const ok = candidate.eps_growth >= 0.25;
                return (
                  <div className="rounded-lg px-2.5 py-2 text-center" style={{ background: "#111111", border: `1px solid ${ok ? "#39ff8f33" : "#1e1e1e"}` }}>
                    <p className="text-[12px] uppercase tracking-widest font-bold mb-0.5" style={{ color: "#6e6e6e" }}>EPS성장</p>
                    <p className="text-sm font-black" style={{ color: ok ? "#39ff8f" : "#9ca3af" }}>{pct(candidate.eps_growth, 0)}</p>
                    <p className="text-[12px]" style={{ color: ok ? "#39ff8f" : "#6b7280" }}>O'Neil {ok ? "✓" : ""}</p>
                  </div>
                );
              })()}
              {candidate.price_vs_52w_high != null && (() => {
                const v = candidate.price_vs_52w_high;
                const ok = v >= -0.05;
                const near = v >= -0.15;
                return (
                  <div className="rounded-lg px-2.5 py-2 text-center" style={{ background: "#111111", border: `1px solid ${ok ? "#39ff8f33" : near ? "#facc1533" : "#1e1e1e"}` }}>
                    <p className="text-[12px] uppercase tracking-widest font-bold mb-0.5" style={{ color: "#6e6e6e" }}>52주 고점</p>
                    <p className="text-sm font-black" style={{ color: ok ? "#39ff8f" : near ? "#facc15" : "#9ca3af" }}>{pct(v, 1)}</p>
                    <p className="text-[12px]" style={{ color: ok ? "#39ff8f" : near ? "#facc15" : "#6b7280" }}>
                      {ok ? "돌파권" : near ? "근접" : ""}
                    </p>
                  </div>
                );
              })()}
            </div>
          )}

          {/* Factor scores */}
          {factors.length > 0 && (
            <div>
              <p className="text-[12px] font-bold uppercase tracking-widest mb-2" style={{ color: "#6e6e6e" }}>팩터 점수</p>
              <div className="space-y-2">
                {factors.map(({ label, val }) => {
                  const v = Math.min(Math.max(val!, 0), 100);
                  const barColor = v >= 70 ? "#39ff8f" : v >= 50 ? "#facc15" : "#ef4444";
                  return (
                    <div key={label} className="flex items-center gap-3">
                      <span className="text-[12px] w-36 shrink-0" style={{ color: "#a8a8a8" }}>{label}</span>
                      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "#202020" }}>
                        <div className="h-full rounded-full" style={{ width: `${v}%`, background: barColor }} />
                      </div>
                      <span className="text-[12px] w-6 text-right font-bold shrink-0" style={{ color: barColor }}>{Math.round(v)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* AI thesis */}
          {candidate.thesis && (
            <div>
              <p className="text-[12px] font-bold uppercase tracking-widest mb-2" style={{ color: "#6e6e6e" }}>AI 분석</p>
              <p className="text-[12px] leading-relaxed" style={{ color: "#d1d5db" }}>{candidate.thesis}</p>
            </div>
          )}

          {/* Catalysts + Bear cases */}
          {(catalysts.length > 0 || bearCases.length > 0) && (
            <div className="grid grid-cols-2 gap-3">
              {catalysts.length > 0 && (
                <div>
                  <p className="text-[12px] font-bold mb-2" style={{ color: "#39ff8f" }}>상승 촉매</p>
                  <div className="space-y-1.5">
                    {catalysts.map((c, i) => (
                      <div key={i} className="flex gap-1.5">
                        <span className="text-[12px] shrink-0 mt-0.5" style={{ color: "#39ff8f" }}>▲</span>
                        <p className="text-[12px] leading-relaxed" style={{ color: "#a8a8a8" }}>{c}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {bearCases.length > 0 && (
                <div>
                  <p className="text-[12px] font-bold mb-2" style={{ color: "#ef4444" }}>하락 리스크</p>
                  <div className="space-y-1.5">
                    {bearCases.map((c, i) => (
                      <div key={i} className="flex gap-1.5">
                        <span className="text-[12px] shrink-0 mt-0.5" style={{ color: "#ef4444" }}>▼</span>
                        <p className="text-[12px] leading-relaxed" style={{ color: "#a8a8a8" }}>{c}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {candidate.confidence != null && (
            <p className="text-[12px] text-right" style={{ color: "#6e6e6e" }}>
              AI 신뢰도 <span className="font-bold" style={{ color: "#6e6e6e" }}>
                {typeof candidate.confidence === "number"
                ? `${Math.round(candidate.confidence > 1 ? candidate.confidence : candidate.confidence * 100)}%`
                : candidate.confidence}
              </span>
            </p>
          )}

          {/* Buy button */}
          <button
            onClick={onBuy}
            className="w-full rounded-xl py-3 text-sm font-black"
            style={{ background: `${accentColor}18`, color: accentColor, border: `1px solid ${accentColor}33` }}
          >
            매수하기 →
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Setup Modal ────────────────────────────────────────────────────────────────
function SetupModal({ market, onDone }: { market: string; onDone: () => void }) {
  const [capital, setCapital] = useState(market === "KR" ? "10000000" : "10000");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setLoading(true);
    setError("");
    const res = await fetch(`/api/paper/${market.toLowerCase()}/setup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_capital: Number(capital) }),
    });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류 발생"); setLoading(false); return; }
    onDone();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.8)" }}>
      <div className="rounded-2xl p-6 w-80" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <h2 className="text-sm font-bold text-white mb-1">페이퍼 포트폴리오 설정</h2>
        <p className="text-[12px] mb-4" style={{ color: "#6e6e6e" }}>
          {market === "KR" ? "가상 원화 자금을 설정합니다" : "가상 달러 자금을 설정합니다"}
        </p>
        <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>
          초기 자금 ({market === "KR" ? "₩" : "$"})
        </label>
        <input
          type="number"
          value={capital}
          onChange={(e) => setCapital(e.target.value)}
          className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none mb-4"
          style={{ background: "#222222", border: "1px solid #2e2e2e" }}
        />
        {error && <p className="text-[12px] text-red-400 mb-2">{error}</p>}
        <button
          onClick={submit}
          disabled={loading}
          className="w-full rounded-lg py-2 text-sm font-bold"
          style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}
        >
          {loading ? "설정 중…" : "시작하기"}
        </button>
      </div>
    </div>
  );
}

// ── Buy Modal ──────────────────────────────────────────────────────────────────
function BuyModal({ candidate, market, onDone, onClose }: {
  candidate: any;
  market: string;
  onDone: () => void;
  onClose: () => void;
}) {
  const defaultPrice = candidate.price ?? "";
  const [price, setPrice] = useState(String(defaultPrice));
  const [shares, setShares] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const total = Number(price) * Number(shares);

  async function submit() {
    setLoading(true);
    setError("");
    const res = await fetch(`/api/paper/${market.toLowerCase()}/buy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: candidate.symbol,
        name: candidate.name,
        shares: Number(shares),
        price: Number(price),
        grade: candidate.grade,
        sector: candidate.sector,
      }),
    });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류 발생"); setLoading(false); return; }
    onDone();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-white">{candidate.symbol} 매수</h2>
            <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{candidate.name}</p>
          </div>
          {candidate.grade && (
            <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#39ff8f18", color: "#39ff8f" }}>
              {candidate.grade}등급
            </span>
          )}
        </div>

        <div className="rounded-lg px-3 py-2.5 mb-4 text-[12px]" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
          <div className="flex justify-between mb-1">
            <span style={{ color: "#6e6e6e" }}>현재 가격</span>
            <span className="text-white font-bold">{candidate.price ? fmt(candidate.price, market) : "—"}</span>
          </div>
          <div className="flex justify-between mb-1">
            <span style={{ color: "#6e6e6e" }}>자동 손절가 (-7.5%)</span>
            <span style={{ color: "#ef4444" }}>
              {Number(price) > 0 ? fmt(Number(price) * 0.925, market) : "—"}
            </span>
          </div>
          <div className="flex justify-between">
            <span style={{ color: "#6e6e6e" }}>합계</span>
            <span className="text-white font-bold">{total > 0 ? fmt(total, market) : "—"}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>
              매수가
            </label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>
              수량 ({market === "KR" ? "주" : "shares"})
            </label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
        </div>

        {error && <p className="text-[12px] text-red-400 mb-2">{error}</p>}
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222222", color: "#6e6e6e" }}>
            취소
          </button>
          <button
            onClick={submit}
            disabled={loading || !price || !shares}
            className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}
          >
            {loading ? "처리 중…" : "매수 확인"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Sell Modal ─────────────────────────────────────────────────────────────────
function SellModal({ position, market, onDone, onClose }: {
  position: any;
  market: string;
  onDone: () => void;
  onClose: () => void;
}) {
  const [price, setPrice] = useState(String(position.current_price ?? position.avg_price));
  const [shares, setShares] = useState(String(position.shares));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const total = Number(price) * Number(shares);
  const pnl = total - Number(shares) * position.avg_price;
  const costBase = Number(shares) * position.avg_price;
  const pnlPct = costBase !== 0 ? pnl / costBase : 0;

  async function submit() {
    setLoading(true);
    setError("");
    const res = await fetch(`/api/paper/${market.toLowerCase()}/sell`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: position.symbol, shares: Number(shares), price: Number(price), note: "manual" }),
    });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류 발생"); setLoading(false); return; }
    onDone();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-white">{position.symbol} 매도</h2>
            <p className="text-[12px]" style={{ color: "#6e6e6e" }}>보유 {position.shares}주 · 평단 {fmt(position.avg_price, market)}</p>
          </div>
        </div>

        <div className="rounded-lg px-3 py-2.5 mb-4 text-[12px]" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
          <div className="flex justify-between mb-1">
            <span style={{ color: "#6e6e6e" }}>예상 손익</span>
            <span style={{ color: pnl >= 0 ? "#39ff8f" : "#ef4444" }} className="font-bold">
              {total > 0 ? `${pnl >= 0 ? "+" : ""}${fmt(pnl, market)} (${pct(pnlPct)})` : "—"}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>매도가</label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>수량</label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              max={position.shares}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
        </div>

        {error && <p className="text-[12px] text-red-400 mb-2">{error}</p>}
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222222", color: "#6e6e6e" }}>
            취소
          </button>
          <button
            onClick={submit}
            disabled={loading}
            className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444433" }}
          >
            {loading ? "처리 중…" : "매도 확인"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Positions Tab ──────────────────────────────────────────────────────────────
function PositionsTab({ data, market, onRefresh }: { data: any; market: string; onRefresh: () => void }) {
  const [sellTarget, setSellTarget] = useState<any>(null);
  const positions: any[] = data?.positions ?? [];
  const summary = data?.summary;

  const alertPositions = positions.filter((p) => p.stop_loss_hit);

  return (
    <div className="space-y-3">
      {/* Stop loss alerts */}
      {alertPositions.length > 0 && (
        <div className="rounded-xl p-3" style={{ background: "#ef444410", border: "1px solid #ef444430" }}>
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} style={{ color: "#ef4444" }} />
            <p className="text-[12px] font-bold" style={{ color: "#ef4444" }}>손절가 도달 종목</p>
          </div>
          {alertPositions.map((p) => (
            <div key={p.symbol} className="flex items-center justify-between text-[12px]">
              <span className="font-bold text-white">{p.symbol}</span>
              <span style={{ color: "#ef4444" }}>
                현재 {fmt(p.current_price, market)} / 손절가 {fmt(p.stop_loss, market)}
              </span>
              <button
                onClick={() => setSellTarget(p)}
                className="ml-3 text-[12px] font-bold px-2 py-0.5 rounded"
                style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444433" }}
              >
                매도
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Summary bar */}
      {summary && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "총 평가액", value: fmt(summary.total_value, market), sub: `초기 ${fmt(data.portfolio.initial_capital, market)}`, color: "var(--text-primary)" },
            { label: "총 손익", value: pct(summary.total_pnl_pct), sub: `${summary.total_pnl >= 0 ? "+" : ""}${fmt(summary.total_pnl, market)}`, color: summary.total_pnl >= 0 ? "#39ff8f" : "#ef4444" },
            { label: "현금", value: fmt(summary.cash, market), sub: `투자중 ${fmt(summary.invested, market)}`, color: "#facc15" },
          ].map(({ label, value, sub, color }) => (
            <div key={label} className="rounded-xl p-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-[12px] uppercase tracking-widest font-bold mb-1" style={{ color: "#6e6e6e" }}>{label}</p>
              <p className="text-lg font-black" style={{ color }}>{value}</p>
              <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>{sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Positions list */}
      {positions.length === 0 ? (
        <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
          <p className="text-sm font-bold text-white mb-1">보유 종목 없음</p>
          <p className="text-[12px]" style={{ color: "#6e6e6e" }}>AI 추천 후보 탭에서 종목을 매수하세요</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ background: "#1c1c1c", borderBottom: "1px solid #2e2e2e" }}>
                {["종목", "등급", "수량", "평단가", "현재가", "손익", "손절가", ""].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-left text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const pnlColor = p.unrealized_pnl >= 0 ? "#39ff8f" : "#ef4444";
                return (
                  <tr key={p.symbol} style={{ borderBottom: "1px solid #151515", background: p.stop_loss_hit ? "#ef444408" : "transparent" }}>
                    <td className="px-3 py-2.5">
                      <p className="font-black text-white">{p.symbol}</p>
                      <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{p.name ?? ""}</p>
                    </td>
                    <td className="px-3 py-2.5">
                      {p.grade && (
                        <span className="text-[12px] font-bold px-1.5 py-0.5 rounded" style={{ background: "#39ff8f18", color: "#39ff8f" }}>
                          {p.grade}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-white">{p.shares}</td>
                    <td className="px-3 py-2.5" style={{ color: "#a8a8a8" }}>{fmt(p.avg_price, market)}</td>
                    <td className="px-3 py-2.5 text-white font-semibold">{fmt(p.current_price, market)}</td>
                    <td className="px-3 py-2.5 font-bold" style={{ color: pnlColor }}>
                      {pct(p.unrealized_pnl_pct)}
                    </td>
                    <td className="px-3 py-2.5" style={{ color: p.stop_loss_hit ? "#ef4444" : "#4b5563" }}>
                      {fmt(p.stop_loss, market)}
                      {p.stop_loss_hit && <span className="ml-1 text-[12px] font-bold">!</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => setSellTarget(p)}
                        className="text-[12px] font-bold px-2 py-1 rounded"
                        style={{ background: "#222222", color: "#a8a8a8", border: "1px solid #2e2e2e" }}
                      >
                        매도
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {sellTarget && (
        <SellModal
          position={sellTarget}
          market={market}
          onClose={() => setSellTarget(null)}
          onDone={() => { setSellTarget(null); onRefresh(); }}
        />
      )}
    </div>
  );
}

// ── Candidates Tab ─────────────────────────────────────────────────────────────
function CandidatesTab({ market, cash, onRefresh }: { market: string; cash: number; onRefresh: () => void }) {
  const [candidates, setCandidates] = useState<any[]>([]);
  const [date, setDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailTarget, setDetailTarget] = useState<any>(null);
  const [buyTarget, setBuyTarget] = useState<any>(null);

  useEffect(() => {
    fetch(`/api/paper/${market.toLowerCase()}/candidates`)
      .then((r) => r.json())
      .then((d) => { setCandidates(d.candidates ?? []); setDate(d.date); setLoading(false); })
      .catch(() => setLoading(false));
  }, [market]);

  if (loading) return <p className="text-sm" style={{ color: "#6e6e6e" }}>로딩 중…</p>;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[12px] font-bold text-white">AI 추천 매수 후보</p>
          <p className="text-[12px]" style={{ color: "#6e6e6e" }}>
            {date ? `${date} 분석 기준` : "분석 데이터 없음"} · BUY / SMALL BUY 등급
          </p>
        </div>
        <div className="text-[12px] rounded-lg px-3 py-1.5" style={{ background: "#222222", color: "#facc15" }}>
          가용현금 {fmt(cash, market)}
        </div>
      </div>

      {candidates.length === 0 ? (
        <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
          <p className="text-sm font-bold text-white mb-1">추천 종목 없음</p>
          <p className="text-[12px]" style={{ color: "#6e6e6e" }}>분석을 실행하면 BUY 등급 종목이 자동으로 표시됩니다</p>
        </div>
      ) : (
        <div className="space-y-2">
          {candidates.map((c) => {
            // null price = no live data, still allow buy (user enters price in modal)
            const canAfford = c.price == null || c.price <= cash;
            return (
              <div
                key={c.symbol}
                className="rounded-xl p-3.5 flex items-center gap-3 cursor-pointer transition-all"
                style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}
                onClick={() => setDetailTarget(c)}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-black text-white">{c.symbol}</span>
                    {c.grade && (
                      <span className="text-[12px] font-bold px-1.5 py-0.5 rounded" style={{ background: "#39ff8f18", color: "#39ff8f" }}>
                        {c.grade}
                      </span>
                    )}
                    <span className="text-[12px] font-bold px-1.5 py-0.5 rounded"
                      style={{ background: c.action === "BUY" ? "#39ff8f18" : "#facc1518", color: c.action === "BUY" ? "#39ff8f" : "#facc15" }}>
                      {c.action}
                    </span>
                  </div>
                  <p className="text-[12px] truncate" style={{ color: "#6e6e6e" }}>{c.name} {c.sector ? `· ${c.sector}` : ""}</p>
                  <div className="flex gap-3 mt-1.5 text-[12px]">
                    {c.composite_score != null && (
                      <span style={{ color: "#a8a8a8" }}>점수 <span className="text-white font-bold">{c.composite_score.toFixed(0)}</span></span>
                    )}
                    {c.peg_ratio != null && (
                      <span style={{ color: c.peg_ratio < (market === "KR" ? 0.7 : 1.0) ? "#39ff8f" : "#f97316" }}>
                        PEG <span className="font-bold">{c.peg_ratio.toFixed(2)}</span>
                      </span>
                    )}
                    {c.eps_growth != null && (
                      <span style={{ color: c.eps_growth >= 0.25 ? "#39ff8f" : "#9ca3af" }}>
                        EPS <span className="font-bold">{pct(c.eps_growth, 0)}</span>
                      </span>
                    )}
                    {c.price_vs_52w_high != null && (
                      <span style={{ color: c.price_vs_52w_high >= -0.15 ? "#39ff8f" : "#9ca3af" }}>
                        52W <span className="font-bold">{pct(c.price_vs_52w_high, 1)}</span>
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-black text-white mb-1.5">
                    {c.price != null ? fmt(c.price, market) : "—"}
                  </p>
                  <button
                    onClick={(e) => { e.stopPropagation(); setBuyTarget(c); }}
                    disabled={!canAfford}
                    className="text-[12px] font-bold px-3 py-1.5 rounded-lg"
                    style={canAfford
                      ? { background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }
                      : { background: "#222222", color: "#6e6e6e", cursor: "not-allowed" }
                    }
                  >
                    {canAfford ? "매수" : "현금부족"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {detailTarget && !buyTarget && (
        <CandidateDetailModal
          candidate={detailTarget}
          market={market}
          onClose={() => setDetailTarget(null)}
          onBuy={() => { setBuyTarget(detailTarget); setDetailTarget(null); }}
        />
      )}

      {buyTarget && (
        <BuyModal
          candidate={buyTarget}
          market={market}
          onClose={() => setBuyTarget(null)}
          onDone={() => { setBuyTarget(null); onRefresh(); }}
        />
      )}
    </div>
  );
}

// ── Trades Tab ─────────────────────────────────────────────────────────────────
function TradesTab({ market }: { market: string }) {
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/paper/${market.toLowerCase()}/trades`)
      .then((r) => r.json())
      .then((d) => { setTrades(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [market]);

  const sells = trades.filter((t) => t.action === "SELL");
  const totalRealizedPnl = sells.reduce((s, t) => s + (t.realized_pnl ?? 0), 0);
  const winCount = sells.filter((t) => (t.realized_pnl ?? 0) > 0).length;
  const winRate = sells.length > 0 ? winCount / sells.length : null;

  if (loading) return <p className="text-sm" style={{ color: "#6e6e6e" }}>로딩 중…</p>;

  return (
    <div className="space-y-3">
      {/* Stats */}
      {sells.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "실현 손익", value: `${totalRealizedPnl >= 0 ? "+" : ""}${fmt(totalRealizedPnl, market)}`, color: totalRealizedPnl >= 0 ? "#39ff8f" : "#ef4444" },
            { label: "승률", value: winRate != null ? `${(winRate * 100).toFixed(0)}%` : "—", color: "#facc15" },
            { label: "총 매도 횟수", value: String(sells.length), color: "#a8a8a8" },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl p-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-[12px] uppercase tracking-widest font-bold mb-1" style={{ color: "#6e6e6e" }}>{label}</p>
              <p className="text-base font-black" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {trades.length === 0 ? (
        <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
          <p className="text-sm font-bold text-white mb-1">거래 내역 없음</p>
          <p className="text-[12px]" style={{ color: "#6e6e6e" }}>종목을 매수하면 여기에 기록됩니다</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ background: "#1c1c1c", borderBottom: "1px solid #2e2e2e" }}>
                {["일시", "종목", "구분", "수량", "가격", "손익", "메모"].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-left text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => {
                const isBuy = t.action === "BUY";
                const pnlColor = !isBuy && (t.realized_pnl ?? 0) >= 0 ? "#39ff8f" : "#ef4444";
                return (
                  <tr key={t.id} style={{ borderBottom: "1px solid #151515" }}>
                    <td className="px-3 py-2.5" style={{ color: "#6e6e6e" }}>
                      {t.traded_at?.slice(0, 16).replace("T", " ")}
                    </td>
                    <td className="px-3 py-2.5">
                      <p className="font-black text-white">{t.symbol}</p>
                      <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{t.name ?? ""}</p>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="text-[12px] font-bold px-1.5 py-0.5 rounded"
                        style={isBuy
                          ? { background: "#39ff8f18", color: "#39ff8f" }
                          : { background: "#ef444418", color: "#ef4444" }
                        }>
                        {isBuy ? "매수" : "매도"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-white">{t.shares}</td>
                    <td className="px-3 py-2.5" style={{ color: "#a8a8a8" }}>{fmt(t.price, market)}</td>
                    <td className="px-3 py-2.5 font-bold" style={{ color: isBuy ? "#4b5563" : pnlColor }}>
                      {isBuy ? "—" : `${(t.realized_pnl ?? 0) >= 0 ? "+" : ""}${fmt(t.realized_pnl ?? 0, market)}`}
                    </td>
                    <td className="px-3 py-2.5 text-[12px]" style={{ color: "#6e6e6e" }}>{t.note ?? ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Add Position Modal ─────────────────────────────────────────────────────────
type LookupCandidate = { symbol: string; name: string | null; current_price: number | null; sector: string | null; source: "analysis" | "yahoo" };

function AddPositionModal({ market, onDone, onClose }: { market: string; onDone: () => void; onClose: () => void }) {
  const isKR = market === "KR";
  // Selected stock
  const [selected, setSelected] = useState<LookupCandidate | null>(null);
  // Search input
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<LookupCandidate[]>([]);
  const [searching, setSearching] = useState(false);
  // Position inputs
  const [price, setPrice] = useState("");
  const [shares, setShares] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function fmtPrice(v: number) {
    return isKR ? `₩${Math.round(v).toLocaleString("ko-KR")}` : `$${v.toFixed(2)}`;
  }

  function handleQueryChange(val: string) {
    setQuery(val);
    setSelected(null);
    setCandidates([]);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!val.trim()) return;
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`/api/real/${market.toLowerCase()}/lookup?q=${encodeURIComponent(val)}`);
        const data = await res.json();
        const list: LookupCandidate[] = data.candidates ?? [];
        setCandidates(list);
        // Auto-select if exact 1 match
        if (list.length === 1) handleSelect(list[0]);
      } catch {
        setCandidates([]);
      } finally {
        setSearching(false);
      }
    }, 400);
  }

  function handleSelect(c: LookupCandidate) {
    setSelected(c);
    setQuery(`${c.symbol}${c.name ? ` · ${c.name}` : ""}`);
    setCandidates([]);
    if (c.current_price != null && !price) setPrice(String(c.current_price));
  }

  const total = Number(price) * Number(shares);

  async function submit() {
    setLoading(true);
    setError("");
    const res = await fetch(`/api/real/${market.toLowerCase()}/positions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: selected?.symbol ?? query.split(" ")[0].toUpperCase(),
        name: selected?.name ?? null,
        shares: Number(shares),
        avg_price: Number(price),
        note: note || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류 발생"); setLoading(false); return; }
    onDone();
  }

  const canSubmit = !loading && (selected != null || query.trim().length >= 1) && Number(price) > 0 && Number(shares) > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white">종목 추가</h2>
          <button onClick={onClose} className="text-[13px] font-bold" style={{ color: "#6e6e6e" }}>✕</button>
        </div>

        {/* Search input */}
        <div className="mb-1 relative">
          <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>
            종목 검색 (코드 또는 종목명)
          </label>
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              placeholder={isKR ? "삼성전자 또는 005930" : "Apple 또는 AAPL"}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none pr-8"
              style={{ background: "#222222", border: `1px solid ${selected ? "#39ff8f44" : "#333"}` }}
              autoFocus
            />
            {searching
              ? <span className="absolute right-2.5 top-2 text-[12px]" style={{ color: "#6e6e6e" }}>…</span>
              : <Search size={13} className="absolute right-2.5 top-2.5" style={{ color: "#6e6e6e" }} />
            }
          </div>

          {/* Dropdown candidates */}
          {candidates.length > 0 && (
            <div className="absolute z-10 w-full mt-1 rounded-xl overflow-hidden" style={{ background: "#131313", border: "1px solid #2e2e2e" }}>
              {candidates.map((c) => (
                <button
                  key={c.symbol}
                  onClick={() => handleSelect(c)}
                  className="w-full px-3 py-2.5 text-left flex items-center justify-between hover:bg-white/5 transition-colors"
                >
                  <div>
                    <span className="text-[12px] font-bold text-white">{c.symbol}</span>
                    {c.name && <span className="ml-2 text-[12px]" style={{ color: "#6e6e6e" }}>{c.name}</span>}
                    {c.sector && <span className="ml-1 text-[12px]" style={{ color: "#4a4a4a" }}>· {c.sector}</span>}
                  </div>
                  <div className="text-right shrink-0 ml-3">
                    {c.current_price != null && (
                      <span className="text-[12px] font-bold" style={{ color: "#39ff8f" }}>{fmtPrice(c.current_price)}</span>
                    )}
                    {c.source === "yahoo" && (
                      <span className="block text-[12px]" style={{ color: "#4a4a4a" }}>YF</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* No results */}
          {!searching && query.trim().length >= 2 && candidates.length === 0 && !selected && (
            <p className="text-[12px] mt-1.5" style={{ color: "#6e6e6e" }}>검색 결과 없음 · 코드를 직접 입력해 추가 가능</p>
          )}
        </div>

        {/* Selected stock info */}
        {selected && (
          <div className="rounded-lg px-3 py-2 mt-2 mb-2 text-[12px] flex justify-between items-center" style={{ background: "#0a1a0a", border: "1px solid #39ff8f22" }}>
            <span className="font-bold text-white">{selected.name ?? selected.symbol}</span>
            <div className="text-right">
              {selected.current_price != null && <span style={{ color: "#39ff8f" }}>{fmtPrice(selected.current_price)}</span>}
              {selected.source === "yahoo" && <span className="block text-[12px]" style={{ color: "#6e6e6e" }}>Yahoo Finance</span>}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 mb-2 mt-3">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>매수 평균가</label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>보유 수량</label>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
        </div>

        {total > 0 && (
          <div className="rounded-lg px-3 py-2 mb-2 text-[12px] flex justify-between" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
            <span style={{ color: "#6e6e6e" }}>투자 원금</span>
            <span className="font-bold text-white">
              {isKR ? `₩${Math.round(total).toLocaleString("ko-KR")}` : `$${total.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            </span>
          </div>
        )}

        <div className="mb-4">
          <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>메모 (선택)</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="예: 분할매수 1차"
            className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
            style={{ background: "#222222", border: "1px solid #2e2e2e" }}
          />
        </div>

        {error && <p className="text-[12px] text-red-400 mb-2">{error}</p>}
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222222", color: "#6e6e6e" }}>취소</button>
          <button
            onClick={submit}
            disabled={!canSubmit}
            className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: canSubmit ? "#39ff8f18" : "#1a1a1a", color: canSubmit ? "#39ff8f" : "#374151", border: canSubmit ? "1px solid #39ff8f33" : "1px solid #2a2a2a" }}
          >
            {loading ? "추가 중…" : "추가하기"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Real Sell Modal ────────────────────────────────────────────────────────────
function RealSellModal({ position, market, onDone, onClose }: {
  position: any;
  market: string;
  onDone: () => void;
  onClose: () => void;
}) {
  const isKR = market === "KR";
  const [price, setPrice] = useState(String(position.current_price ?? position.avg_price));
  const [shares, setShares] = useState(String(position.shares));
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function fmtLocal(v: number) {
    return isKR ? `₩${Math.round(v).toLocaleString("ko-KR")}` : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  const total = Number(price) * Number(shares);
  const pnl = total - Number(shares) * position.avg_price;
  const costBase = Number(shares) * position.avg_price;
  const pnlPct = costBase !== 0 ? pnl / costBase : 0;

  async function submit() {
    setLoading(true);
    setError("");
    const res = await fetch(`/api/real/${market.toLowerCase()}/sell`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: position.symbol,
        shares: Number(shares),
        sell_price: Number(price),
        note: note || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류 발생"); setLoading(false); return; }
    onDone();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-white">{position.symbol} 매도</h2>
            <p className="text-[12px]" style={{ color: "#6e6e6e" }}>보유 {position.shares}주 · 평단 {fmtLocal(position.avg_price)}</p>
          </div>
          <button onClick={onClose} className="text-[13px] font-bold" style={{ color: "#6e6e6e" }}>✕</button>
        </div>

        <div className="rounded-lg px-3 py-2.5 mb-4 text-[12px]" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
          <div className="flex justify-between">
            <span style={{ color: "#6e6e6e" }}>예상 실현 손익</span>
            <span style={{ color: total > 0 ? (pnl >= 0 ? "#39ff8f" : "#ef4444") : "#4b5563" }} className="font-bold">
              {total > 0 ? `${pnl >= 0 ? "+" : ""}${fmtLocal(pnl)} (${pnl >= 0 ? "+" : ""}${(pnlPct * 100).toFixed(2)}%)` : "—"}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-2">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>매도가</label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>수량</label>
            <input
              type="number"
              value={shares}
              max={position.shares}
              onChange={(e) => setShares(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222222", border: "1px solid #2e2e2e" }}
            />
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>메모 (선택)</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="예: 목표가 도달 매도"
            className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
            style={{ background: "#222222", border: "1px solid #2e2e2e" }}
          />
        </div>

        {error && <p className="text-[12px] text-red-400 mb-2">{error}</p>}
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222222", color: "#6e6e6e" }}>취소</button>
          <button
            onClick={submit}
            disabled={loading || !price || !shares}
            className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444433" }}
          >
            {loading ? "처리 중…" : "매도 확인"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Real Trades Tab ────────────────────────────────────────────────────────────
function RealTradesTab({ market }: { market: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/real/${market.toLowerCase()}/trades`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [market]);

  const isKR = market === "KR";
  const trades: any[] = data?.trades ?? [];
  const stats = data?.stats;

  function fmtLocal(v: number) {
    return isKR ? `₩${Math.round(v).toLocaleString("ko-KR")}` : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  if (loading) return <p className="text-sm" style={{ color: "#6e6e6e" }}>로딩 중…</p>;

  return (
    <div className="space-y-3">
      {stats && stats.sell_count > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "실현 손익", value: `${(stats.total_realized_pnl ?? 0) >= 0 ? "+" : ""}${fmtLocal(stats.total_realized_pnl ?? 0)}`, color: (stats.total_realized_pnl ?? 0) >= 0 ? "#39ff8f" : "#ef4444" },
            { label: "승률", value: stats.win_rate != null ? `${(stats.win_rate * 100).toFixed(0)}%` : "—", color: "#facc15" },
            { label: "매도 횟수", value: String(stats.sell_count), color: "#a8a8a8" },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl p-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-[12px] uppercase tracking-widest font-bold mb-1" style={{ color: "#6e6e6e" }}>{label}</p>
              <p className="text-base font-black" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {trades.length === 0 ? (
        <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
          <p className="text-sm font-bold text-white mb-1">거래 내역 없음</p>
          <p className="text-[12px]" style={{ color: "#6e6e6e" }}>종목을 추가하거나 매도하면 여기에 기록됩니다</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ background: "#1c1c1c", borderBottom: "1px solid #2e2e2e" }}>
                {["일시", "종목", "구분", "수량", "단가", "금액", "실현손익", "메모"].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-left text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => {
                const isBuy = t.action === "BUY";
                const pnlColor = (t.realized_pnl ?? 0) >= 0 ? "#39ff8f" : "#ef4444";
                return (
                  <tr key={t.id} style={{ borderBottom: "1px solid #151515" }}>
                    <td className="px-3 py-2.5" style={{ color: "#6e6e6e" }}>
                      {t.traded_at?.slice(0, 16).replace("T", " ")}
                    </td>
                    <td className="px-3 py-2.5">
                      <p className="font-black text-white">{t.symbol}</p>
                      <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{t.name ?? ""}</p>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="text-[12px] font-bold px-1.5 py-0.5 rounded"
                        style={isBuy
                          ? { background: "#39ff8f18", color: "#39ff8f" }
                          : { background: "#ef444418", color: "#ef4444" }}>
                        {isBuy ? "매수" : "매도"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-white">{t.shares}</td>
                    <td className="px-3 py-2.5" style={{ color: "#a8a8a8" }}>{fmtLocal(t.price)}</td>
                    <td className="px-3 py-2.5" style={{ color: "#a8a8a8" }}>{fmtLocal(t.total_amount)}</td>
                    <td className="px-3 py-2.5 font-bold" style={{ color: isBuy ? "#4b5563" : pnlColor }}>
                      {isBuy ? "—" : `${(t.realized_pnl ?? 0) >= 0 ? "+" : ""}${fmtLocal(t.realized_pnl ?? 0)} (${(t.realized_pnl ?? 0) >= 0 ? "+" : ""}${((t.realized_pnl_pct ?? 0) * 100).toFixed(2)}%)`}
                    </td>
                    <td className="px-3 py-2.5 text-[12px]" style={{ color: "#6e6e6e" }}>{t.note ?? ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Real Portfolio Section ──────────────────────────────────────────────────────
type RealTab = "positions" | "trades";

function RealPortfolioSection({ market }: { market: string }) {
  const [realTab, setRealTab] = useState<RealTab>("positions");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [sellTarget, setSellTarget] = useState<any>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    fetch(`/api/real/${market.toLowerCase()}/positions`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [market]);

  useEffect(() => { refresh(); setRealTab("positions"); }, [market, refresh]);

  async function handleDelete(symbol: string) {
    await fetch(`/api/real/${market.toLowerCase()}/positions?symbol=${encodeURIComponent(symbol)}`, { method: "DELETE" });
    refresh();
  }

  const isKR = market === "KR";
  const positions: any[] = data?.positions ?? [];
  const summary = data?.summary;

  function fmtLocal(v: number) {
    return isKR ? `₩${Math.round(v).toLocaleString("ko-KR")}` : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  const REAL_TABS: { id: RealTab; label: string }[] = [
    { id: "positions", label: "보유 종목" },
    { id: "trades", label: "거래 내역" },
  ];

  return (
    <div className="space-y-3">
      {/* Summary */}
      {summary && positions.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "투자 원금", value: fmtLocal(summary.total_cost), color: "#a8a8a8" },
            { label: "총 평가액", value: fmtLocal(summary.total_value), color: "var(--text-primary)" },
            { label: "평가 손익", value: `${summary.total_pnl >= 0 ? "+" : ""}${(summary.total_pnl_pct * 100).toFixed(2)}%`, sub: `${summary.total_pnl >= 0 ? "+" : ""}${fmtLocal(summary.total_pnl)}`, color: summary.total_pnl >= 0 ? "#39ff8f" : "#ef4444" },
          ].map(({ label, value, sub, color }) => (
            <div key={label} className="rounded-xl p-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-[12px] uppercase tracking-widest font-bold mb-1" style={{ color: "#6e6e6e" }}>{label}</p>
              <p className="text-base font-black" style={{ color }}>{value}</p>
              {sub && <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>{sub}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Tab bar + Add button */}
      <div className="flex items-center justify-between">
        <div className="flex rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e", width: "fit-content" }}>
          {REAL_TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setRealTab(id)}
              className="px-5 py-2 text-[12px] font-semibold transition-colors"
              style={{
                background: realTab === id ? "#facc1518" : "transparent",
                color: realTab === id ? "#facc15" : "#6b7280",
                borderRight: id === "positions" ? "1px solid #1e1e1e" : undefined,
              }}
            >
              {label}
            </button>
          ))}
        </div>
        {realTab === "positions" && (
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-1.5 rounded-lg"
            style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}
          >
            <Plus size={12} /> 매수 추가
          </button>
        )}
      </div>

      {/* Positions tab */}
      {realTab === "positions" && (
        loading ? (
          <p className="text-sm" style={{ color: "#6e6e6e" }}>로딩 중…</p>
        ) : positions.length === 0 ? (
          <div className="rounded-xl p-10 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
            <DollarSign size={28} className="mx-auto mb-2" style={{ color: "#39ff8f" }} />
            <p className="text-sm font-bold text-white mb-1">보유 종목이 없습니다</p>
            <p className="text-[12px] mb-4" style={{ color: "#6e6e6e" }}>매수 추가 버튼을 눌러 실제 보유 종목을 등록하세요</p>
            <button
              onClick={() => setShowAdd(true)}
              className="text-sm font-bold px-4 py-2 rounded-xl"
              style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}
            >
              + 첫 종목 추가하기
            </button>
          </div>
        ) : (
          <>
            {/* 모바일 카드 뷰 */}
            <div className="md:hidden space-y-2">
              {positions.map((p) => {
                const hasCurrent = p.current_price != null;
                const pnlColor = !hasCurrent ? "#4b5563" : (p.unrealized_pnl ?? 0) >= 0 ? "#39ff8f" : "#ef4444";
                return (
                  <div key={p.symbol} className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <p className="font-black text-white">{p.symbol}</p>
                        {p.name && <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{p.name}</p>}
                      </div>
                      <p className="text-xl font-black" style={{ color: pnlColor }}>
                        {p.unrealized_pnl_pct != null
                          ? `${p.unrealized_pnl_pct >= 0 ? "+" : ""}${(p.unrealized_pnl_pct * 100).toFixed(2)}%`
                          : "—"}
                      </p>
                    </div>
                    <div className="grid grid-cols-3 gap-3 mb-3 text-[12px]">
                      <div>
                        <p style={{ color: "#6e6e6e" }}>보유수량</p>
                        <p className="font-bold text-white mt-0.5">{p.shares}</p>
                      </div>
                      <div>
                        <p style={{ color: "#6e6e6e" }}>평단가</p>
                        <p className="font-bold text-white mt-0.5">{fmtLocal(p.avg_price)}</p>
                      </div>
                      <div>
                        <p style={{ color: "#6e6e6e" }}>현재가</p>
                        <p className="font-bold mt-0.5" style={{ color: hasCurrent ? "#fff" : "#4a4a4a" }}>
                          {hasCurrent ? fmtLocal(p.current_price) : "—"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[12px]" style={{ color: "#6e6e6e" }}>
                        평가액 <span className="font-semibold text-white">
                          {p.market_value != null ? fmtLocal(p.market_value) : fmtLocal(p.cost_basis)}
                        </span>
                      </span>
                      <div className="flex items-center gap-2">
                        <button onClick={() => setSellTarget(p)} className="text-[12px] font-bold px-3 py-1.5 rounded-lg"
                          style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444430" }}>
                          매도
                        </button>
                        <button onClick={() => handleDelete(p.symbol)} className="p-1.5 rounded" style={{ color: "#4a4a4a" }}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 데스크톱 테이블 */}
            <div className="hidden md:block rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
              <table className="w-full text-[13px]">
                <thead>
                  <tr style={{ background: "#1c1c1c", borderBottom: "1px solid #2e2e2e" }}>
                    {["종목", "수량", "평단가", "현재가", "평가액", "손익", ""].map((h) => (
                      <th key={h} className="px-3 py-2.5 text-left text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => {
                    const hasCurrent = p.current_price != null;
                    const pnlColor = !hasCurrent ? "#4b5563" : (p.unrealized_pnl ?? 0) >= 0 ? "#39ff8f" : "#ef4444";
                    return (
                      <tr key={p.symbol} style={{ borderBottom: "1px solid #151515" }}>
                        <td className="px-3 py-2.5">
                          <p className="font-black text-white">{p.symbol}</p>
                          <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{p.name ?? ""}</p>
                          {p.note && <p className="text-[12px] mt-0.5" style={{ color: "#4a4a4a" }}>{p.note}</p>}
                        </td>
                        <td className="px-3 py-2.5 text-white">{p.shares}</td>
                        <td className="px-3 py-2.5" style={{ color: "#a8a8a8" }}>{fmtLocal(p.avg_price)}</td>
                        <td className="px-3 py-2.5">
                          {hasCurrent ? (
                            <div>
                              <span className="text-white font-semibold">{fmtLocal(p.current_price)}</span>
                              {p.price_source === "yahoo" && (
                                <span className="ml-1 text-[8px] font-bold" style={{ color: "#6e6e6e" }}>YF</span>
                              )}
                            </div>
                          ) : (
                            <span className="text-[12px]" style={{ color: "#4a4a4a" }}>가격 없음</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5" style={{ color: "#a8a8a8" }}>
                          {p.market_value != null ? fmtLocal(p.market_value) : fmtLocal(p.cost_basis)}
                        </td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: pnlColor }}>
                          {p.unrealized_pnl_pct != null
                            ? `${p.unrealized_pnl_pct >= 0 ? "+" : ""}${(p.unrealized_pnl_pct * 100).toFixed(2)}%`
                            : "—"}
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <button onClick={() => setSellTarget(p)} className="text-[12px] font-bold px-2 py-1 rounded"
                              style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444430" }}>
                              매도
                            </button>
                            <button onClick={() => handleDelete(p.symbol)} className="p-1 rounded" style={{ color: "#4a4a4a" }} title="데이터 삭제 (거래 미기록)">
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )
      )}

      {/* Trades tab */}
      {realTab === "trades" && <RealTradesTab market={market} />}

      {showAdd && (
        <AddPositionModal
          market={market}
          onClose={() => setShowAdd(false)}
          onDone={() => { setShowAdd(false); refresh(); }}
        />
      )}

      {sellTarget && (
        <RealSellModal
          position={sellTarget}
          market={market}
          onClose={() => setSellTarget(null)}
          onDone={() => { setSellTarget(null); refresh(); }}
        />
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function PortfolioPage() {
  const { market } = useMarket();
  const [mode, setMode] = useState<Mode>("real");
  const [tab, setTab] = useState<Tab>("positions");
  const [portfolioData, setPortfolioData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    fetch(`/api/paper/${market.toLowerCase()}/portfolio`)
      .then((r) => r.json())
      .then((d) => { setPortfolioData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [market]);

  useEffect(() => {
    refresh();
    setTab("positions");
  }, [market, refresh]);

  const TABS: { id: Tab; label: string }[] = [
    { id: "positions", label: "보유 포지션" },
    { id: "candidates", label: "AI 추천 후보" },
    { id: "trades", label: "거래 내역" },
  ];

  const isKR = market === "KR";
  const cash = portfolioData?.summary?.cash ?? portfolioData?.portfolio?.cash ?? 0;

  return (
    <div className="space-y-3 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
              <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
            </span>
            <h1 className="text-base font-bold text-white">포트폴리오</h1>
          </div>
          <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>
            {mode === "real" ? "실제 보유 종목을 등록하고 수익률을 추적합니다" : "가상 자금으로 AI 추천 종목을 사고팔며 전략을 검증합니다"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {mode === "paper" && (
            <>
              <button
                onClick={refresh}
                className="p-1.5 rounded-lg"
                style={{ background: "#222222", color: "#6e6e6e" }}
              >
                <RefreshCw size={14} />
              </button>
              <button
                onClick={() => setShowSetup(true)}
                className="text-[12px] font-bold px-3 py-1.5 rounded-lg"
                style={{ background: "#222222", color: "#a8a8a8", border: "1px solid #2e2e2e" }}
              >
                {portfolioData?.exists ? "재설정" : "초기 설정"}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Mode toggle */}
      <div className="flex rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e", width: "fit-content" }}>
        {(["real", "paper"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className="px-5 py-2 text-[12px] font-bold transition-colors"
            style={{
              background: mode === m ? "#facc1518" : "transparent",
              color: mode === m ? "#facc15" : "#6b7280",
              borderRight: m === "real" ? "1px solid #1e1e1e" : undefined,
            }}
          >
            {m === "real" ? "실제 보유" : "페이퍼 트레이딩"}
          </button>
        ))}
      </div>

      {/* Real portfolio mode */}
      {mode === "real" && <RealPortfolioSection market={market} />}

      {/* Paper trading mode */}
      {mode === "paper" && (
        <>
          {/* Not configured */}
          {!loading && !portfolioData?.exists && (
            <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <DollarSign size={32} className="mx-auto mb-2" style={{ color: "#39ff8f" }} />
              <p className="text-sm font-bold text-white mb-1">포트폴리오가 설정되지 않았습니다</p>
              <p className="text-[12px] mb-4" style={{ color: "#6e6e6e" }}>
                가상 자금을 설정하고 AI 추천 종목을 테스트해 보세요
              </p>
              <button
                onClick={() => setShowSetup(true)}
                className="text-sm font-bold px-5 py-2 rounded-xl"
                style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}
              >
                시작하기
              </button>
            </div>
          )}

          {/* Tabs */}
          {portfolioData?.exists && (
            <>
              <div className="flex rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e", width: "fit-content" }}>
                {TABS.map(({ id, label }) => (
                  <button
                    key={id}
                    onClick={() => setTab(id)}
                    className="px-5 py-2 text-[12px] font-semibold transition-colors"
                    style={{
                      background: tab === id ? "#39ff8f18" : "transparent",
                      color: tab === id ? "#39ff8f" : "#6b7280",
                      borderRight: id !== "trades" ? "1px solid #1e1e1e" : undefined,
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {tab === "positions" && <PositionsTab data={portfolioData} market={market} onRefresh={refresh} />}
              {tab === "candidates" && <CandidatesTab market={market} cash={cash} onRefresh={refresh} />}
              {tab === "trades" && <TradesTab market={market} />}
            </>
          )}
        </>
      )}

      {showSetup && (
        <SetupModal
          market={market}
          onDone={() => { setShowSetup(false); refresh(); }}
        />
      )}
    </div>
  );
}
