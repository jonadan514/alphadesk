"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { Trash2, Plus, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";
import { stopLossPct } from "@/src/lib/stopLoss";

type TradeType = "buy" | "sell";
interface DecisionSnapshot {
  snapshot_at: string;
  checklist: string | null;
  grade: string | null;
  composite_score: number | null;
  gate: string | null;
  regime: string | null;
}
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
  decision_snapshot: DecisionSnapshot | null;
}
interface ChartPoint {
  date: string;
  myPortfolio: number | null;
  benchmark: number | null;
}

type Tab = "trades" | "performance";

const MARKET_OPTS = ["US", "KR"];
const TYPE_OPTS: { value: TradeType; label: string; color: string }[] = [
  { value: "buy",  label: "매수", color: "#ffb020" },
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
    <div className="rounded-xl px-3 py-2 text-[12px] space-y-1" style={{ background: "#111009", border: "1px solid #262112" }}>
      <p style={{ color: "#726b58" }}>{label}</p>
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

  // 펀더멘털 장기(1~3년) 시뮬레이션 포트폴리오의 큰 폭 하락·재무 훼손 알림.
  // 자동 매도는 없고 참고용 — 어차피 손절선이 아니라 사용자 판단이 최종 결정.
  const [alerts, setAlerts] = useState<{ symbol: string; alert_type: string; detail: any; alert_date: string }[]>([]);
  const loadAlerts = useCallback(async () => {
    const res = await fetch("/api/portfolio/alerts?days=30").then((r) => r.json()).catch(() => null);
    setAlerts(Array.isArray(res?.alerts) ? res.alerts : []);
  }, []);
  useEffect(() => { loadAlerts(); }, [loadAlerts]);

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

  // 매수체크 "포트폴리오에 기록" CTA가 넘긴 값으로 매수 폼을 미리 채워 연다.
  // 실제 체결가는 사용자가 확인·수정 후 저장 (자동 생성하지 않음).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    const symbol = sp.get("symbol");
    if (!symbol) return;
    setForm((f) => ({
      ...f,
      market: sp.get("market") === "KR" ? "KR" : "US",
      symbol: symbol.toUpperCase(),
      name: sp.get("name") ?? f.name,
      type: "buy",
      price: sp.get("price") ?? f.price,
      shares: sp.get("shares") ?? f.shares,
      note: sp.get("note") ?? f.note,
    }));
    setTab("trades");
    setShowForm(true);
  }, []);

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
  const holdings = useMemo(() => {
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
  }, [trades]);

  // 보유 종목 현재가 조회
  const [prices, setPrices] = useState<Record<string, number | null>>({});
  useEffect(() => {
    const keys = holdings.map((h) => `${h.market}:${h.symbol}`);
    if (keys.length === 0) { setPrices({}); return; }
    fetch(`/api/portfolio/prices?symbols=${keys.join(",")}`)
      .then((r) => r.json())
      .then(setPrices)
      .catch(() => {});
  }, [holdings]);

  const fmtMoney = (market: string, v: number) =>
    market === "US" ? `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : `₩${Math.round(v).toLocaleString()}`;

  // 보유 시장의 현재 체제 → 손절 기준(%) 조회
  const [regimes, setRegimes] = useState<Record<string, string>>({});
  useEffect(() => {
    const markets = Array.from(new Set(holdings.map((h) => h.market)));
    if (markets.length === 0) return;
    Promise.allSettled(
      markets.map((m) =>
        fetch(m === "KR" ? "/api/data/kr/regime" : "/api/data/regime").then((r) => r.json())
      )
    ).then((results) => {
      const next: Record<string, string> = {};
      markets.forEach((m, i) => {
        const r = results[i];
        if (r.status === "fulfilled") next[m] = r.value?.regime ?? "neutral";
      });
      setRegimes(next);
    });
  }, [holdings]);

  // 시장별 합계 (가격 조회된 종목만)
  const totals = useMemo(() => {
    const acc: Record<string, { cost: number; value: number }> = {};
    for (const h of holdings) {
      const price = prices[`${h.market}:${h.symbol}`];
      if (price == null) continue;
      const a = (acc[h.market] ??= { cost: 0, value: 0 });
      a.cost += h.cost * h.shares;
      a.value += price * h.shares;
    }
    return acc;
  }, [holdings, prices]);

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
                background: tab === t ? "#ffb02018" : "transparent",
                color: tab === t ? "#ffb020" : "#726b58",
                border: `1px solid ${tab === t ? "#ffb02033" : "transparent"}`,
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
            <div className="rounded-xl p-3 space-y-2" style={{ background: "#111009", border: "1px solid #262112" }}>
              <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "#423e33" }}>현재 보유</p>
              {holdings.map((h) => {
                const price = prices[`${h.market}:${h.symbol}`];
                const pl    = price != null ? (price - h.cost) * h.shares : null;
                const plPct = price != null && h.cost > 0 ? (price / h.cost - 1) * 100 : null;
                const plColor = pl == null ? "#423e33" : pl >= 0 ? "#4ade80" : "#f87171";

                const threshold = stopLossPct(regimes[h.market]);   // 예: 8 (= -8% 손절선)
                const breached  = plPct != null && plPct <= -threshold;
                const near      = !breached && plPct != null && plPct <= -threshold + 2;   // 손절선 2%p 이내로 근접
                const distToStop = plPct != null ? plPct - (-threshold) : null;             // 손절선까지 남은 %p (0 이하 = 도달)

                return (
                  <div key={`${h.market}:${h.symbol}`} className="py-1" style={{ borderTop: "1px solid #262112" }}>
                    <div className="flex items-center justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-bold shrink-0" style={{ background: "#262112", color: "#a39c88" }}>{h.market}</span>
                          <span className="text-[13px] font-bold text-white">{h.symbol}</span>
                          {h.name && <span className="text-[11px] truncate" style={{ color: "#726b58" }}>{h.name}</span>}
                        </div>
                        <p className="text-[11px] mt-0.5" style={{ color: "#423e33" }}>
                          {h.shares.toLocaleString()}주 · 평단 {fmtMoney(h.market, h.cost)}
                        </p>
                      </div>
                      <div className="text-right shrink-0 ml-3">
                        {price != null ? (
                          <>
                            <p className="text-[13px] font-bold text-white">{fmtMoney(h.market, price)}</p>
                            <p className="text-[11px] font-bold" style={{ color: plColor }}>
                              {plPct != null ? `${plPct >= 0 ? "+" : ""}${plPct.toFixed(1)}%` : ""}
                              {pl != null ? ` (${pl >= 0 ? "+" : "-"}${fmtMoney(h.market, Math.abs(pl))})` : ""}
                            </p>
                          </>
                        ) : (
                          <p className="text-[11px]" style={{ color: "#423e33" }}>가격 조회 중…</p>
                        )}
                      </div>
                    </div>
                    {(breached || near) && (
                      <div className="flex items-center gap-1.5 mt-1 rounded-lg px-2 py-1"
                        style={{ background: breached ? "#f8717118" : "#fb923c18", border: `1px solid ${breached ? "#f8717140" : "#fb923c40"}` }}>
                        <AlertTriangle size={11} color={breached ? "#f87171" : "#fb923c"} />
                        <span className="text-[11px] font-bold" style={{ color: breached ? "#f87171" : "#fb923c" }}>
                          {breached
                            ? `손절선(-${threshold}%) 도달 — 매도 규칙 재확인`
                            : `손절선까지 ${distToStop != null ? Math.abs(distToStop).toFixed(1) : "?"}%p 남음`}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}

              {/* 시장별 합계 */}
              {Object.keys(totals).length > 0 && (
                <div className="pt-2 space-y-1" style={{ borderTop: "1px solid #262112" }}>
                  {Object.entries(totals).map(([market, t]) => {
                    const pl = t.value - t.cost;
                    const pct = t.cost > 0 ? (pl / t.cost) * 100 : 0;
                    const color = pl >= 0 ? "#4ade80" : "#f87171";
                    return (
                      <div key={market} className="flex items-center justify-between">
                        <span className="text-[11px] font-bold" style={{ color: "#726b58" }}>{market} 합계</span>
                        <span className="text-[12px]">
                          <span className="font-bold text-white">{fmtMoney(market, t.value)}</span>
                          <span className="ml-2 font-bold" style={{ color }}>
                            {pl >= 0 ? "+" : "-"}{fmtMoney(market, Math.abs(pl))} ({pct >= 0 ? "+" : ""}{pct.toFixed(1)}%)
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* 장기 페이퍼 포트폴리오 알림 — 자동매도 없이 참고용으로만 */}
          {alerts.length > 0 && (
            <div className="rounded-xl p-3 space-y-2" style={{ background: "#111009", border: "1px solid #f8717133" }}>
              <div className="flex items-center gap-1.5">
                <AlertTriangle size={12} color="#f87171" />
                <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "#f87171" }}>
                  장기 시뮬레이션 보유 알림 (자동매도 없음, 참고용)
                </p>
              </div>
              {alerts.map((a, i) => (
                <div key={i} className="flex items-center justify-between py-1" style={{ borderTop: i > 0 ? "1px solid #262112" : "none" }}>
                  <div className="min-w-0">
                    <span className="text-[12px] font-bold text-white">{a.symbol}</span>
                    <span className="text-[11px] ml-2" style={{ color: "#726b58" }}>
                      {a.alert_type === "price_drawdown"
                        ? `매수가 대비 ${a.detail.pnl_pct != null ? (a.detail.pnl_pct * 100).toFixed(1) : "?"}% 하락`
                        : `재무 훼손: ${Array.isArray(a.detail.red_flags) ? a.detail.red_flags.join(", ") : "확인 필요"}`}
                    </span>
                  </div>
                  <span className="text-[10px] shrink-0" style={{ color: "#423e33" }}>{a.alert_date}</span>
                </div>
              ))}
              <p className="text-[10px]" style={{ color: "#423e33" }}>
                손절선이 아니라 사용자 판단으로 매도 여부를 결정하세요 — 정상적인 조정인지, 논지가 실제로 깨졌는지 구분이 먼저입니다.
              </p>
            </div>
          )}

          {/* 추가 버튼 */}
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-medium transition-all"
            style={{ background: "#111009", color: "#ffb020", border: "1px solid #262112" }}
          >
            <Plus size={13} />
            거래 추가
          </button>

          {/* 입력 폼 */}
          {showForm && (
            <div className="rounded-xl p-4 space-y-3" style={{ background: "#111009", border: "1px solid #262112" }}>
              <div className="grid grid-cols-2 gap-2">
                {/* 마켓 */}
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>마켓</label>
                  <div className="flex gap-1">
                    {MARKET_OPTS.map((m) => (
                      <button key={m} onClick={() => setForm((f) => ({ ...f, market: m }))}
                        className="flex-1 py-1.5 rounded-lg text-[12px] font-bold"
                        style={{ background: form.market === m ? "#ffb02018" : "#262112", color: form.market === m ? "#ffb020" : "#726b58", border: `1px solid ${form.market === m ? "#ffb02033" : "transparent"}` }}>
                        {m}
                      </button>
                    ))}
                  </div>
                </div>
                {/* 매수/매도 */}
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>유형</label>
                  <div className="flex gap-1">
                    {TYPE_OPTS.map((o) => (
                      <button key={o.value} onClick={() => setForm((f) => ({ ...f, type: o.value }))}
                        className="flex-1 py-1.5 rounded-lg text-[12px] font-bold"
                        style={{ background: form.type === o.value ? `${o.color}18` : "#262112", color: form.type === o.value ? o.color : "#726b58", border: `1px solid ${form.type === o.value ? `${o.color}33` : "transparent"}` }}>
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>종목 코드</label>
                  <input value={form.symbol} onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value.toUpperCase() }))}
                    placeholder={form.market === "KR" ? "005930" : "AAPL"}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0d0c07", color: "#ece7d8", border: "1px solid #262112" }} />
                </div>
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>종목명 (선택)</label>
                  <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder={form.market === "KR" ? "삼성전자" : "Apple"}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0d0c07", color: "#ece7d8", border: "1px solid #262112" }} />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>날짜</label>
                  <input type="date" value={form.trade_date} onChange={(e) => setForm((f) => ({ ...f, trade_date: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0d0c07", color: "#ece7d8", border: "1px solid #262112" }} />
                </div>
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>가격</label>
                  <input type="number" value={form.price} onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
                    placeholder="0"
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0d0c07", color: "#ece7d8", border: "1px solid #262112" }} />
                </div>
                <div>
                  <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>수량</label>
                  <input type="number" value={form.shares} onChange={(e) => setForm((f) => ({ ...f, shares: e.target.value }))}
                    placeholder="0"
                    className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                    style={{ background: "#0d0c07", color: "#ece7d8", border: "1px solid #262112" }} />
                </div>
              </div>

              <div>
                <label className="text-[11px] mb-1 block" style={{ color: "#726b58" }}>메모 (선택)</label>
                <input value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
                  placeholder="매수 이유, 전략 등"
                  className="w-full px-3 py-2 rounded-lg text-[13px] outline-none"
                  style={{ background: "#0d0c07", color: "#ece7d8", border: "1px solid #262112" }} />
              </div>

              <div className="flex gap-2">
                <button onClick={addTrade} disabled={saving || !form.symbol || !form.price || !form.shares}
                  className="flex-1 py-2 rounded-lg text-[13px] font-bold transition-opacity disabled:opacity-40"
                  style={{ background: "#ffb02018", color: "#ffb020", border: "1px solid #ffb02033" }}>
                  {saving ? "저장 중…" : "저장"}
                </button>
                <button onClick={() => setShowForm(false)}
                  className="px-4 py-2 rounded-lg text-[13px]"
                  style={{ background: "#262112", color: "#726b58" }}>
                  취소
                </button>
              </div>
            </div>
          )}

          {/* 거래 목록 */}
          {trades.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: "#111009", border: "1px solid #262112" }}>
              <p className="text-sm" style={{ color: "#423e33" }}>아직 거래 기록이 없습니다.<br />위 버튼으로 첫 거래를 추가해보세요.</p>
            </div>
          ) : (
            <div className="rounded-xl overflow-hidden" style={{ background: "#111009", border: "1px solid #262112" }}>
              {trades.map((t, i) => (
                <div key={t.id}
                  className="flex items-center justify-between px-4 py-3"
                  style={{ borderTop: i > 0 ? "1px solid #262112" : "none" }}>
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                      style={{ background: t.type === "buy" ? "#4ade8018" : "#f8717118", color: t.type === "buy" ? "#4ade80" : "#f87171" }}>
                      {t.type === "buy" ? "매수" : "매도"}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[13px] font-bold text-white">{t.symbol}</span>
                        {t.name && <span className="text-[11px] truncate" style={{ color: "#726b58" }}>{t.name}</span>}
                        <span className="text-[10px] px-1 rounded shrink-0" style={{ background: "#262112", color: "#a39c88" }}>{t.market}</span>
                      </div>
                      <div className="text-[11px] mt-0.5" style={{ color: "#423e33" }}>
                        {t.trade_date} · {t.shares.toLocaleString()}주 · {t.market === "US" ? `$${t.price.toFixed(2)}` : `₩${Math.round(t.price).toLocaleString()}`}
                        {t.note && <span className="ml-2" style={{ color: "#726b58" }}>{t.note}</span>}
                      </div>
                      {t.type === "buy" && t.decision_snapshot && (
                        <div className="text-[10px] mt-1 flex items-center gap-1 flex-wrap" style={{ color: "#726b58" }}>
                          <span title="매수 시점에 고정된 기록 — 이후 수정 불가">🔒 매수 시점</span>
                          {t.decision_snapshot.grade && (
                            <span className="px-1 rounded" style={{ background: "#262112", color: "#ffb020" }}>
                              {t.decision_snapshot.grade}등급
                            </span>
                          )}
                          {t.decision_snapshot.gate && (
                            <span className="px-1 rounded" style={{ background: "#262112" }}>{t.decision_snapshot.gate}</span>
                          )}
                          {(() => {
                            try {
                              const items = t.decision_snapshot.checklist ? JSON.parse(t.decision_snapshot.checklist) : [];
                              const checked = items.filter((it: any) => it.checked).length;
                              return items.length > 0 ? <span>체크 {checked}/{items.length}</span> : null;
                            } catch { return null; }
                          })()}
                        </div>
                      )}
                    </div>
                  </div>
                  <button onClick={() => deleteTrade(t.id)} className="p-1.5 rounded-lg ml-2 shrink-0"
                    style={{ color: "#423e33" }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#f87171")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "#423e33")}>
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
            <div className="rounded-xl p-12 flex items-center justify-center" style={{ background: "#111009", border: "1px solid #262112" }}>
              <div className="w-5 h-5 rounded-full border-2 animate-spin" style={{ borderColor: "#ffb020", borderTopColor: "transparent" }} />
            </div>
          ) : chart && chart.points.length > 0 ? (
            <>
              {/* 요약 카드 */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "내 포트폴리오", value: myReturn, color: "#ffb020" },
                  { label: chart.benchmarkLabel, value: bmReturn, color: "#6fb3b8" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-xl p-3 text-center" style={{ background: "#111009", border: "1px solid #262112" }}>
                    <p className="text-[11px] mb-1" style={{ color: "#726b58" }}>{label}</p>
                    <div className="flex items-center justify-center gap-1">
                      {value != null && (value >= 0
                        ? <TrendingUp size={14} color="#4ade80" />
                        : <TrendingDown size={14} color="#f87171" />)}
                      <p className="text-lg font-black" style={{ color: value == null ? "#423e33" : value >= 0 ? "#4ade80" : "#f87171" }}>
                        {value != null ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "—"}
                      </p>
                    </div>
                    <p className="text-[10px] mt-0.5" style={{ color: "#423e33" }}>첫 거래 이후 누적</p>
                  </div>
                ))}
              </div>

              {/* 차트 */}
              <div className="rounded-xl p-4" style={{ background: "#111009", border: "1px solid #262112" }}>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chart.points} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#262112" />
                    <XAxis dataKey="date" tick={{ fill: "#423e33", fontSize: 10 }}
                      tickFormatter={(v) => v.slice(2, 7)} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: "#423e33", fontSize: 10 }}
                      tickFormatter={(v) => `${(v - 100).toFixed(0)}%`} />
                    <Tooltip content={<ChartTooltip benchmarkLabel={chart.benchmarkLabel} />} />
                    <ReferenceLine y={100} stroke="#262112" strokeDasharray="4 4" />
                    <Legend formatter={(v) => v === "myPortfolio" ? "내 포트폴리오" : chart.benchmarkLabel}
                      wrapperStyle={{ fontSize: 11, color: "#726b58" }} />
                    <Line type="monotone" dataKey="myPortfolio" stroke="#ffb020" strokeWidth={2}
                      dot={false} connectNulls activeDot={{ r: 4 }} />
                    <Line type="monotone" dataKey="benchmark" stroke="#6fb3b8" strokeWidth={1.5}
                      dot={false} connectNulls activeDot={{ r: 3 }} strokeDasharray="5 3" />
                  </LineChart>
                </ResponsiveContainer>
                <p className="text-[10px] mt-2 text-center" style={{ color: "#423e33" }}>
                  기준점: 첫 거래일 = 100 · 주간 종가 기준
                </p>
              </div>
            </>
          ) : trades.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: "#111009", border: "1px solid #262112" }}>
              <p className="text-sm" style={{ color: "#423e33" }}>매매 기록 탭에서 거래를 먼저 입력해주세요.</p>
            </div>
          ) : (
            <div className="rounded-xl p-8 text-center" style={{ background: "#111009", border: "1px solid #262112" }}>
              <p className="text-sm" style={{ color: "#423e33" }}>가격 데이터를 불러오는 중이거나 데이터가 없습니다.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
