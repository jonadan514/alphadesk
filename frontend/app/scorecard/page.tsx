"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";

type Bucket = { fwd_30d: number | null; fwd_60d: number | null; fwd_90d: number | null; n: number };

type ScorecardData = {
  market: string;
  comparison: { benchmark: Bucket; filtered_equal_weight: Bucket; actual_trades: Bucket };
  by_grade: Record<string, Bucket>;
  by_gate: Record<string, Bucket>;
  total_picks: number;
  total_trades: number;
  earliest_date: string | null;
  latest_date: string | null;
};

function pct(v: number | null): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

function pctColor(v: number | null): string {
  if (v == null) return "var(--text-faint)";
  return v >= 0 ? "#4ade80" : "#f87171";
}

export default function ScorecardPage() {
  const { market } = useMarket();
  const [data, setData] = useState<ScorecardData | null>(null);

  useEffect(() => {
    setData(null);
    fetch(`/api/data/scorecard?market=${market}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null));
  }, [market]);

  if (!data) {
    return (
      <div className="bg-card rounded-lg p-3 text-center text-sm" style={{ color: "var(--text-muted)" }}>
        로딩 중…
      </div>
    );
  }

  const indexName = market === "KR" ? "KOSPI" : "SPY";
  const comparisonRows: { key: keyof ScorecardData["comparison"]; label: string; desc: string }[] = [
    { key: "benchmark", label: `${indexName} 단순 보유`, desc: "기준선" },
    { key: "filtered_equal_weight", label: "필터 통과 종목 균등매수", desc: "정량 필터가 값을 더했는가" },
    { key: "actual_trades", label: "실제 매수한 종목", desc: "정성 판단이 값을 더했는가" },
  ];

  return (
    <div className="space-y-2">
      {/* 헤더 */}
      <div className="bg-card rounded-xl p-3">
        <div className="flex items-center gap-2 mb-1">
          <h1 className="text-[18px] font-black" style={{ color: "var(--text-primary)" }}>성적표</h1>
          <InfoTooltip content="과거 픽/거래에 실제 주가를 대조한 사후 검증입니다. 결과가 기대와 다를 수 있고, 그게 이 화면의 목적입니다." />
        </div>
        <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          {data.earliest_date && data.latest_date
            ? `${data.earliest_date} ~ ${data.latest_date}  ·  픽 ${data.total_picks}개  ·  실거래 ${data.total_trades}건`
            : "아직 집계된 데이터가 없습니다 (매주 일요일 자동 집계)."}
        </p>
      </div>

      {/* 3-way 비교 */}
      <div className="bg-card rounded-xl p-3">
        <h2 className="stat-label mb-2">3-way 비교</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ color: "var(--text-muted)" }}>
                <th className="text-left py-1.5 font-semibold">비교 대상</th>
                <th className="text-right py-1.5 font-semibold">30일 후</th>
                <th className="text-right py-1.5 font-semibold">60일 후</th>
                <th className="text-right py-1.5 font-semibold">90일 후</th>
                <th className="text-right py-1.5 font-semibold">표본수</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map(({ key, label, desc }) => {
                const b = data.comparison[key];
                return (
                  <tr key={key} style={{ borderTop: "1px solid var(--border)" }}>
                    <td className="py-2">
                      <div className="font-semibold" style={{ color: "var(--text-primary)" }}>{label}</div>
                      <div className="text-[11px]" style={{ color: "var(--text-faint)" }}>{desc}</div>
                    </td>
                    <td className="text-right font-mono font-bold" style={{ color: pctColor(b.fwd_30d) }}>{pct(b.fwd_30d)}</td>
                    <td className="text-right font-mono font-bold" style={{ color: pctColor(b.fwd_60d) }}>{pct(b.fwd_60d)}</td>
                    <td className="text-right font-mono font-bold" style={{ color: pctColor(b.fwd_90d) }}>{pct(b.fwd_90d)}</td>
                    <td className="text-right font-mono" style={{ color: "var(--text-faint)" }}>{b.n}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {data.comparison.actual_trades.n === 0 && (
          <p className="text-[11px] mt-2" style={{ color: "var(--text-faint)" }}>
            실제 매수 기록이 없거나 아직 30일이 지나지 않았습니다. 포트폴리오 페이지에서 거래를 기록하면 여기 채워집니다.
          </p>
        )}
      </div>

      {/* 등급별 */}
      <div className="bg-card rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <h2 className="stat-label">등급별 이후 30일 수익률</h2>
          <InfoTooltip content="등급(A~F) 구분이 실제 수익률 순서와 대응하는지 확인합니다." />
        </div>
        <div className="grid grid-cols-5 gap-2">
          {Object.entries(data.by_grade).map(([grade, b]) => (
            <div key={grade} className="rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <p className="text-[13px] font-black" style={{ color: "var(--text-primary)" }}>{grade}</p>
              <p className="text-[16px] font-black font-mono mt-1" style={{ color: pctColor(b.fwd_30d) }}>{pct(b.fwd_30d)}</p>
              <p className="text-[11px] mt-0.5" style={{ color: "var(--text-faint)" }}>n={b.n}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 게이트별 */}
      <div className="bg-card rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <h2 className="stat-label">게이트 상태별 이후 30일 시장 수익률</h2>
          <InfoTooltip content="마켓 게이트의 GO/CAUTION/STOP 구분이 실제로 의미가 있는지 확인합니다." />
        </div>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(data.by_gate).map(([gate, b]) => (
            <div key={gate} className="rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <p className="text-[13px] font-black" style={{ color: "var(--text-primary)" }}>{gate}</p>
              <p className="text-[16px] font-black font-mono mt-1" style={{ color: pctColor(b.fwd_30d) }}>{pct(b.fwd_30d)}</p>
              <p className="text-[11px] mt-0.5" style={{ color: "var(--text-faint)" }}>n={b.n}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-card rounded-xl p-3">
        <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>
          손절 발동 종목의 손절 후 주가 추이는 페이퍼 포트폴리오 거래 이력이 충분히 쌓인 뒤 추가될 예정입니다 (최근 저장 버그를 수정해 이제부터 이력이 축적됩니다).
        </p>
      </div>
    </div>
  );
}
