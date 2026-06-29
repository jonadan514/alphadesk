"use client";

import { useEffect, useState, useCallback } from "react";
import { Trash2, Plus, TrendingUp, TrendingDown } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";

type TradeType = "buy" | "sell";
interface Trade {
  id: number;
  market: string;
  symbol: string;
  name: string | null;
  type: TradeType;
  trade_date: string;
  price: number;
  shares: number;
  note: string | null;
}
interface ChartPoint {
  date: string;
  myPortfolio: number | null;
  benchmark: number | null;
}

type Tab = "trades" | "performance";

const MARKET_OPTS = ["US", "KR"];
const TYPE_OPTS: { value: TradeType; label: string; color: string }[] = [
  { value: "buy",  label: "매수", color: "#39ff8f" },
  { value: "sell", label: "매도", color: "#f87171" },
];

function today() {
  return new Date().toISOString().split("T")[0];
}

function pctLabel(v: number | null | undefined) {
  if (v == null) return "—";
  const diff = v - 100;
  const sign = diff >= 0 ? "+" : "";
  return `${sign}${diff.toFixed(2)}%`;
}

// ── Custom chart tooltip ───────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label, benchmarkLabel }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl px-3 py-2 text-[12px] space-y-1" style={{ background: "#1c1c1c", border: "1px solid #333" }}>
      <p style={{ color: "#6b7280" }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.dataKey === "myPortfolio" ? "내 포트폴리오" : benchmarkLabel} : {p.value != null ? pctLabel(p.value) : "—"}
        </p>
      ))}
    </div>
  );
}

export default function PortfolioPage() {
  const [tab, setTab] = useState<Tab>("trades");
  const [trades, setTrades] = useState<Trade[]>([]);
  const [chart, setChart] = useState<{ points: ChartPoint[]; benchmarkLabel: string } | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    market: "US", symbol: "", name: "", type: "buy" as TradeType,
    trade_date: today(), price: "", shares: "", note: "",
  });

  const loadTrades = useCallback(async () => {
    const res = await fetch("/api/trades").then((r) => r.json()).catch(() => []);
    setTrades(Array.isArray(res) ? res : []);
  }, []);

  const loadChart = useCallback(async () => {
    setChartLoading(true);
    const res = await fetch("/api/portfolio/performance").then((r) => r.json()).catch(() => null);
    if (res && Array.isArray(res.dates)) {
      const points: ChartPoint[] = res.dates.map((d: string, i: number) => ({
        date: d,
        myPortfolio: res.myPortfolio[i] ?? null,
        benchmark: res.benchmark[i] ?? null,
      }));
      setChart({ points, benchmarkLabel: res.benchmarkLabel ?? "SPY" });
    }
    setChartLoading(false);
  }, []);

  useEffect(() => { loadTrades(); }, [loadTrades]);
  useEffect(() => { if (tab === "performance") loadChart(); }, [tab, loadChart]);

  async function addTrade() {
    if (!form.symbol || !form.price || !form.shares) return;
    setSaving(true);
    await fetch("/api/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, price: Number(form.price), shares: Number(form.shares) }),
    });
    setSaving(false);
    setShowForm(false);
    setForm({ market: "US", symbol: "", name: "", type: "buy", trade_date: today(), price: "", shares: "", note: "" });
    loadTrades();
  }

  async function deleteTrade(id: number) {
    await fetch(`/api/trades/${id}`, { method: "DELETE" });
    loadTrades();
  }

  // Compute holdings summary from trades
  const holdings = (() => {
    const map = new Map<string, { market: string; name: string | null; shares: number; cost: number }>();
    [...trades].reverse().forEach((t) => {
      const key = `${t.market}:${t.symbol}`;
      const cur = map.get(key) ?? { market: t.market, name: t.name, shares: 0, cost: 0 };
      if (t.type === "buy") {
        cur.cost = (cur.cost * cur.shares + t.price * t.shares) / (cur.shares + t.shares || 1);
        cur.shares += t.shares;
      } else {
        cur.shares = Math.max(0, cur.shares - t.shares);
      }
      map.set(key, cur);
    });
    return Array.from(map.entries())
      .filter(([, v]) => v.shares > 0)
      .map(([key, v]) => ({ symbol: key.split(":")[1], ...v }));
  })();

  const lastChart = chart?.points.at(-1);
  const myReturn = lastChart?.myPortfolio != null ? lastChart.myPortfolio - 100 : null;
  const bmReturn = lastChart?.benchmark != null ? lastChart.benchmark - 100 : null;

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-bold text-white">포트폴리오</h1>
        <div className="flex gap-1">
          {(["trades", "performance"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-3 py-1 rounded-lg text-[12px] font-medium transition-all"
              style={{
                background: tab === t ? "#fbbf2418" : "transparent",
                color: tab === t ? "#fbbf24" : "#6b7280",
                border: `1px solid ${tab === t ? "#fbbf2433" : "transparent"}`,
              }}
            >
              {t === "trades" ? "매매 기록" : "성과 비교"}
            </button>
          ))}
        </div>
      </div>

      {/* ── 매매 기록 탭 ── */}
      {tab === "trades" && (
        <div className="space-y-3">
          {/* 현재 보유 */}
          {holdings.length > 0 && (
            <div className="rounded-xl p-3 space-y-2" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "#4b5563" }}>현재 보유</p>
              {holdings.map((h) => (
                <div key={h.symbol} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-bold" style={{ background: "#2e2e2e", color: "#9ca3af" }}>{h.market}</span>
                    <span className="text-[13px] font-bold text-white">{h.symbol}</span>
                    {h.name && <span className="text-[11px]" style={{ color: "#6b7280" }}>{h.name}</span>}
                  </div>
                  <span className="text-[12px]" style={{ color: "#9ca3af" }}>
                    {h.shares.toLocaleString()}주 · 평균 {h.market === "US" ? `$${h.cost.toFixed(2)}` : `₩${Math.round(h.cost).toLocaleString()}`}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* 추가 버튼 */}
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-medium transition-all"
            style={{ background: "#1c1c1c", color: "#fbbf24", border: "1px solid #2e2e2e" }}
          >
            <Plus size={13} />
            거래 추가
          </button>

          {/* 입력 폼 */}
          {showForm && (
            <div className="rounded-xl p-4 space-y-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <div className="grid grid-cols-2 gap-2">
                {/* 마켓 */}
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>마켓</label>
                  <div className="flex gap-1">
                    {MARKET_OPTS.map((m) => (
                      <button key={m} onClick={() => setForm((f) => ({ ...f, market: m }))}
                        className="flex-1 py-1.5 rounded-lg text-[12px] font-bold"
                        style={{ background: form.market === m ? "#fbbf2418" : "#2a2a2a", color: form.market === m ? "#fbbf24" : "#6b7280", border: `1px solid ${form.market === m ? "#fbbf2433" : "transparent"}` }}>
                        {m}
                      </button>
                    ))}
                  </div>
                </div>
                {/* 매수/매도 */}
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>유형</label>
                  <div className="flex gap-1">
                    {TYPE_OPTS.map((o) => (
                      <button key={o.value} onClick={() => setForm((f) => ({ ...f, type: o.value }))}
                        className="flex-1 py-1.5 rounded-lg text-[12px] font-bold"
                        style={{ background: form.type === o.value ? `${o.color}18` : "#2a2a2a", color: form.type === o.value ? o.color : "#6b7280", border: `1px solid ${form.type === o.value ? `${o.color}33` : "transparent"}` }}>
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>종목 코드</label>
                  <input value={form.symbol} onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value.toUpperCase() }))}
                    placeholder={form.market === "KR" ? "005930" : "AAPL"}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0e0e0e", color: "#e5e7eb", border: "1px solid #333" }} />
                </div>
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>종목명 (선택)</label>
                  <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder={form.market === "KR" ? "삼성전자" : "Apple"}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0e0e0e", color: "#e5e7eb", border: "1px solid #333" }} />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>날짜</label>
                  <input type="date" value={form.trade_date} onChange={(e) => setForm((f) => ({ ...f, trade_date: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0e0e0e", color: "#e5e7eb", border: "1px solid #333" }} />
                </div>
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>가격</label>
                  <input type="number" value={form.price} onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
                    placeholder="0"
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0e0e0e", color: "#e5e7eb", border: "1px solid #333" }} />
                </div>
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>수량</label>
                  <input type="number" value={form.shares} onChange={(e) => setForm((f) => ({ ...f, shares: e.target.value }))}
                    placeholder="0"
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0e0e0e", color: "#e5e7eb", border: "1px solid #333" }} />
                </div>
              </div>

              <div>
                <label className="text-[11px] mb-1 block" style={{ color: "#6b7280" }}>메모 (선택)</label>
                <input value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
                  placeholder="매수 이유, 전략 등"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                  style={{ background: "#0e0e0e", color: "#e5e7eb", border: "1px solid #333" }} />
              </div>

              <div className="flex gap-2">
                <button onClick={addTrade} disabled={saving || !form.symbol || !form.price || !form.shares}
                  className="flex-1 py-2 rounded-lg text-[13px] font-bold transition-opacity disabled:opacity-40"
                  style={{ background: "#fbbf2418", color: "#fbbf24", border: "1px solid #fbbf2433" }}>
                  {saving ? "저장 중…" : "저장"}
                </button>
                <button onClick={() => setShowForm(false)}
                  className="px-4 py-2 rounded-lg text-[13px]"
                  style={{ background: "#2a2a2a", color: "#6b7280" }}>
                  취소
                </button>
              </div>
            </div>
          )}

          {/* 거래 목록 */}
          {trades.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-sm" style={{ color: "#4b5563" }}>아직 거래 기록이 없습니다.<br />위 버튼으로 첫 거래를 추가해보세요.</p>
            </div>
          ) : (
            <div className="rounded-xl overflow-hidden" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              {trades.map((t, i) => (
                <div key={t.id}
                  className="flex items-center justify-between px-4 py-3"
                  style={{ borderTop: i > 0 ? "1px solid #222" : "none" }}>
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                      style={{ background: t.type === "buy" ? "#39ff8f18" : "#ef444418", color: t.type === "buy" ? "#39ff8f" : "#ef4444" }}>
                      {t.type === "buy" ? "매수" : "매도"}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[13px] font-bold text-white">{t.symbol}</span>
                        {t.name && <span className="text-[11px] truncate" style={{ color: "#6b7280" }}>{t.name}</span>}
                        <span className="text-[10px] px-1 rounded shrink-0" style={{ background: "#2e2e2e", color: "#9ca3af" }}>{t.market}</span>
                      </div>
                      <div className="text-[11px] mt-0.5" style={{ color: "#4b5563" }}>
                        {t.trade_date} · {t.shares.toLocaleString()}주 · {t.market === "US" ? `$${t.price.toFixed(2)}` : `₩${Math.round(t.price).toLocaleString()}`}
                        {t.note && <span className="ml-2" style={{ color: "#6b7280" }}>{t.note}</span>}
                      </div>
                    </div>
                  </div>
                  <button onClick={() => deleteTrade(t.id)} className="p-1.5 rounded-lg ml-2 shrink-0"
                    style={{ color: "#4b5563" }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "#4b5563")}>
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── 성과 비교 탭 ── */}
      {tab === "performance" && (
        <div className="space-y-4">
          {chartLoading ? (
            <div className="rounded-xl p-12 flex items-center justify-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <div className="w-5 h-5 rounded-full border-2 animate-spin" style={{ borderColor: "#fbbf24", borderTopColor: "transparent" }} />
            </div>
          ) : chart && chart.points.length > 0 ? (
            <>
              {/* 요약 카드 */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "내 포트폴리오", value: myReturn, color: "#fbbf24" },
                  { label: chart.benchmarkLabel, value: bmReturn, color: "#60a5fa" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-xl p-3 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                    <p className="text-[11px] mb-1" style={{ color: "#6b7280" }}>{label}</p>
                    <div className="flex items-center justify-center gap-1">
                      {value != null && (value >= 0
                        ? <TrendingUp size={14} color="#39ff8f" />
                        : <TrendingDown size={14} color="#ef4444" />)}
                      <p className="text-lg font-black" style={{ color: value == null ? "#4b5563" : value >= 0 ? "#39ff8f" : "#ef4444" }}>
                        {value != null ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "—"}
                      </p>
                    </div>
                    <p className="text-[10px] mt-0.5" style={{ color: "#4b5563" }}>첫 거래 이후 누적</p>
                  </div>
                ))}
              </div>

              {/* 차트 */}
              <div className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chart.points} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                    <XAxis dataKey="date" tick={{ fill: "#4b5563", fontSize: 10 }}
                      tickFormatter={(v) => v.slice(2, 7)} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: "#4b5563", fontSize: 10 }}
                      tickFormatter={(v) => `${(v - 100).toFixed(0)}%`} />
                    <Tooltip content={<ChartTooltip benchmarkLabel={chart.benchmarkLabel} />} />
                    <ReferenceLine y={100} stroke="#333" strokeDasharray="4 4" />
                    <Legend formatter={(v) => v === "myPortfolio" ? "내 포트폴리오" : chart.benchmarkLabel}
                      wrapperStyle={{ fontSize: 11, color: "#6b7280" }} />
                    <Line type="monotone" dataKey="myPortfolio" stroke="#fbbf24" strokeWidth={2}
                      dot={false} connectNulls activeDot={{ r: 4 }} />
                    <Line type="monotone" dataKey="benchmark" stroke="#60a5fa" strokeWidth={1.5}
                      dot={false} connectNulls activeDot={{ r: 3 }} strokeDasharray="5 3" />
                  </LineChart>
                </ResponsiveContainer>
                <p className="text-[10px] mt-2 text-center" style={{ color: "#4b5563" }}>
                  기준점: 첫 거래일 = 100 · 주간 종가 기준
                </p>
              </div>
            </>
          ) : trades.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-sm" style={{ color: "#4b5563" }}>매매 기록 탭에서 거래를 먼저 입력해주세요.</p>
            </div>
          ) : (
            <div className="rounded-xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-sm" style={{ color: "#4b5563" }}>가격 데이터를 불러오는 중이거나 데이터가 없습니다.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
