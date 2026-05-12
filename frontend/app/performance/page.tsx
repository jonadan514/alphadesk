"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";

export default function PerformancePage() {
  const { market } = useMarket();
  const [perfData, setPerfData]       = useState<any>(null);
  const [reports, setReports]         = useState<any[]>([]);
  const [portfolioData, setPortfolio] = useState<any>(null);
  const [aiTargetMap, setAiTargetMap] = useState<Record<string, number>>({});
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    setLoading(true);
    setReports([]);
    setPerfData(null);
    setPortfolio(null);
    setAiTargetMap({});

    if (market === "KR") {
      Promise.allSettled([
        fetch("/api/data/kr/reports?limit=60").then((r) => r.json()),
        fetch("/api/data/kr/ai-summaries").then((r) => r.json()),
      ]).then(([repRes, aiRes]) => {
        if (repRes.status === "fulfilled") setReports(Array.isArray(repRes.value) ? repRes.value : []);
        if (aiRes.status === "fulfilled") {
          const summaries: any[] = aiRes.value?.summaries ?? [];
          const m: Record<string, number> = {};
          summaries.forEach((s: any) => { if (s.ticker && s.target_price) m[s.ticker] = s.target_price; });
          setAiTargetMap(m);
        }
        setLoading(false);
      }).catch(() => setLoading(false));
    } else {
      Promise.allSettled([
        fetch("/api/data/performance").then((r) => r.json()),
        fetch("/api/data/reports?limit=60").then((r) => r.json()),
        fetch("/api/data/portfolio").then((r) => r.json()),
      ]).then(([perfRes, repRes, pfRes]) => {
        if (perfRes.status === "fulfilled") setPerfData(perfRes.value);
        if (repRes.status === "fulfilled")  setReports(repRes.value);
        if (pfRes.status  === "fulfilled")  setPortfolio(pfRes.value);
        setLoading(false);
      });
    }
  }, [market]);

  const chartData = reports
    .slice()
    .reverse()
    .map((r: any) => ({
      date:  r.date?.slice(5),
      picks: (r.picks ?? []).length,
      buy:   (r.picks ?? []).filter((p: any) => p.action === "BUY").length,
    }));

  const buyPicks: any[] = [];
  reports.forEach((r: any) => {
    (r.picks ?? [])
      .filter((p: any) => p.action === "BUY")
      .forEach((p: any) => buyPicks.push({
        ...p,
        report_date: r.date,
        target_price: p.target_price ?? aiTargetMap[p.symbol] ?? null,
      }));
  });

  const snapshotRows: { label: string; value: any }[] = perfData
    ? Object.entries(perfData).map(([k, v]) => ({ label: k.replace(/_/g, " "), value: String(v) }))
    : [];

  const isKR = market === "KR";

  // 벤치마크 비교 차트 데이터 (equal_medium vs SPY vs QQQ)
  const benchmarkChartData = (() => {
    if (!portfolioData) return [];
    const pfHistory: { date: string; pnl_pct: number }[] = portfolioData["equal_medium"]?.history ?? [];
    const spyHistory: { date: string; pnl_pct: number }[] = portfolioData["benchmarks"]?.["SPY"] ?? [];
    const qqqHistory: { date: string; pnl_pct: number }[] = portfolioData["benchmarks"]?.["QQQ"] ?? [];

    const spyMap = Object.fromEntries(spyHistory.map((r) => [r.date, r.pnl_pct]));
    const qqqMap = Object.fromEntries(qqqHistory.map((r) => [r.date, r.pnl_pct]));

    return pfHistory
      .filter((r) => r.date)
      .slice(-90)
      .map((r) => ({
        date:      r.date?.slice(5),
        portfolio: parseFloat(((r.pnl_pct ?? 0) * 100).toFixed(2)),
        spy:       spyMap[r.date] != null ? parseFloat(((spyMap[r.date]) * 100).toFixed(2)) : null,
        qqq:       qqqMap[r.date] != null ? parseFloat(((qqqMap[r.date]) * 100).toFixed(2)) : null,
      }));
  })();

  // 최종 수익률 차이
  const lastBench = benchmarkChartData[benchmarkChartData.length - 1];
  const alphaPct  = lastBench ? (lastBench.portfolio - (lastBench.spy ?? 0)) : null;

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
            <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
          </span>
          <h1 className="text-base font-bold text-white">성과 트래커</h1>
          <InfoTooltip content="분석 리포트에서 BUY 액션으로 선별된 종목의 이력을 추적합니다." />
        </div>
        <p className="text-[12px] text-[#6b7280]">분석 리포트 기반 BUY 추천 이력</p>
      </div>

      {loading && <p className="text-sm text-[#6b7280]">로딩 중…</p>}

      {/* Snapshot KPIs */}
      {snapshotRows.length > 0 && (
        <div className="grid grid-cols-5 gap-3">
          {snapshotRows.map(({ label, value }) => (
            <div key={label} className="bg-card rounded-lg p-3">
              <p className="text-[12px] uppercase tracking-widest text-[#6b7280]">{label}</p>
              <p className="text-xl font-black text-white mt-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* 벤치마크 비교 차트 (US only) */}
      {!isKR && benchmarkChartData.length > 0 && (
        <div className="bg-card rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <p className="text-[12px] font-semibold uppercase tracking-widest text-[#6b7280]">포트폴리오 vs 벤치마크</p>
            <InfoTooltip content="equal_medium 페이퍼 포트폴리오의 누적 수익률을 SPY·QQQ와 비교합니다." />
            {alphaPct !== null && (
              <span className="ml-auto text-[12px] font-bold px-2 py-0.5 rounded" style={{
                color: alphaPct >= 0 ? "#39ff8f" : "#ef4444",
                background: alphaPct >= 0 ? "#39ff8f18" : "#ef444418",
                border: `1px solid ${alphaPct >= 0 ? "#39ff8f44" : "#ef444444"}`
              }}>
                α {alphaPct >= 0 ? "+" : ""}{alphaPct.toFixed(2)}% vs SPY
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={benchmarkChartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#6b7280" }} />
              <YAxis tick={{ fontSize: 9, fill: "#6b7280" }} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: "#131313", border: "1px solid #2e2e2e", fontSize: 11 }}
                formatter={(v) => [`${Number(v).toFixed(2)}%`]}
              />
              <Legend wrapperStyle={{ fontSize: 10, color: "#6e6e6e" }} />
              <ReferenceLine y={0} stroke="#2a2a2a" />
              <Line type="monotone" dataKey="portfolio" stroke="#39ff8f" strokeWidth={2} dot={false} name="Portfolio (eq.med)" />
              <Line type="monotone" dataKey="spy"       stroke="#60a5fa" strokeWidth={1.5} dot={false} name="SPY" />
              <Line type="monotone" dataKey="qqq"       stroke="#c084fc" strokeWidth={1.5} dot={false} name="QQQ" strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="bg-card rounded-lg p-3">
          <p className="text-[12px] font-semibold uppercase tracking-widest text-[#6b7280] mb-2">일별 Pick 추이</p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#6b7280" }} />
              <YAxis tick={{ fontSize: 9, fill: "#6b7280" }} />
              <Tooltip contentStyle={{ background: "#131313", border: "1px solid #2e2e2e", fontSize: 11 }} />
              <ReferenceLine y={0} stroke="#2a2a2a" />
              <Line type="monotone" dataKey="picks" stroke="#facc15" strokeWidth={2} dot={false} name="Total" />
              <Line type="monotone" dataKey="buy"   stroke="#39ff8f" strokeWidth={2} dot={false} name="BUY" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* BUY picks table */}
      {buyPicks.length > 0 && (
        <div className="bg-card rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: "#272727" }}>
            <p className="text-[12px] font-semibold uppercase tracking-widest text-[#6b7280]">BUY 추천 이력</p>
            <span className="text-[13px] text-[#6b7280]">{buyPicks.length}건</span>
          </div>
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ borderBottom: "1px solid #2a2a2a" }}>
                {(isKR
                  ? ["Date", "Symbol", "Name", "Grade", "Score", "Price (KRW)", "Target (AI)", "Sector"]
                  : ["Date", "Symbol", "Grade", "Score", "Current", "Target", "Sector"]
                ).map((h) => (
                  <th key={h} className="px-3 py-2.5 text-left font-semibold uppercase" style={{ color: "#6e6e6e", fontSize: "10px" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {buyPicks.slice(0, 50).map((p: any, i: number) => (
                <tr key={i} style={{ borderBottom: "1px solid #2e2e2e" }}>
                  <td className="px-3 py-2 font-mono text-[#6b7280]">{p.report_date}</td>
                  <td className="px-3 py-2 font-black text-white">{p.symbol}</td>
                  {isKR && (
                    <td className="px-3 py-2 text-[#9ca3af]">{p.name ?? "—"}</td>
                  )}
                  <td className="px-3 py-2" style={{ color: "#39ff8f" }}>{p.grade}</td>
                  <td className="px-3 py-2 font-mono text-white">{p.composite_score}</td>
                  {isKR ? (
                    <>
                      <td className="px-3 py-2 font-mono text-[#9ca3af]">
                        {p.cur_price != null ? `₩${Number(p.cur_price).toLocaleString()}` : "—"}
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: "#39ff8f" }}>
                        {p.target_price != null ? `₩${Number(p.target_price).toLocaleString()}` : "—"}
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-2 font-mono text-[#9ca3af]">
                        {p.current_price != null ? `$${p.current_price.toFixed(2)}` : "—"}
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: "#39ff8f" }}>
                        {p.target_price != null ? `$${p.target_price.toFixed(2)}` : "—"}
                      </td>
                    </>
                  )}
                  <td className="px-3 py-2 text-[#6b7280]">{p.sector}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && buyPicks.length === 0 && snapshotRows.length === 0 && (
        <p className="text-sm text-[#6b7280]">성과 데이터가 없습니다. 분석을 먼저 실행하세요.</p>
      )}
    </div>
  );
}
