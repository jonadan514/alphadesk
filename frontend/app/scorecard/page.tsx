"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";

// scripts/compute_pick_returns.py의 HORIZONS와 반드시 일치해야 함.
const HORIZONS = [30, 60, 90, 180, 365, 730] as const;
const HORIZON_LABEL: Record<number, string> = {
  30: "30일", 60: "60일", 90: "90일", 180: "6개월", 365: "1년", 730: "2년",
};

type Bucket = Record<string, number | null> & { n: number };

type ScorecardData = {
  market: string;
  comparison: { benchmark: Bucket; filtered_equal_weight: Bucket };
  by_piotroski: Record<string, Bucket>;
  total_picks: number;
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
  const [error, setError] = useState<string | null>(null);
  // 등급별/게이트별 카드는 기간 하나를 골라서 보여준다 — 장기 투자 검증이 핵심이라 1년을 기본값으로.
  const [breakdownHorizon, setBreakdownHorizon] = useState<number>(365);

  useEffect(() => {
    setData(null);
    setError(null);
    fetch(`/api/data/scorecard?market=${market}`)
      .then((r) => r.json())
      .then((d) => {
        // API가 { error } 형태(테이블 없음·Turso 오류 등)를 반환할 수도 있으므로
        // comparison 필드 존재로 실제 데이터인지 확인 후에만 렌더링한다.
        if (d && d.comparison) setData(d);
        else setError(typeof d?.error === "string" ? d.error : "데이터를 불러오지 못했습니다.");
      })
      .catch(() => setError("데이터를 불러오지 못했습니다."));
  }, [market]);

  if (error) {
    return (
      <div className="bg-card rounded-lg p-3 text-center text-sm" style={{ color: "var(--text-muted)" }}>
        아직 집계된 데이터가 없습니다. 매주 일요일 자동 배치 실행 후 표시됩니다.
      </div>
    );
  }

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
  ];
  const bdCol = `fwd_${breakdownHorizon}d_ret`;

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
            ? `${data.earliest_date} ~ ${data.latest_date}  ·  픽 ${data.total_picks}개`
            : "아직 집계된 데이터가 없습니다 (매주 일요일 자동 집계)."}
        </p>
      </div>

      {/* 2-way 비교 — 30일~2년까지 한 번에 (단기 30/60/90 스윙 검증, 180일 이후는 장기 펀더멘털 검증) */}
      <div className="bg-card rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <h2 className="stat-label">2-way 비교</h2>
          <InfoTooltip content="180일(6개월)부터는 1~3년 펀더멘털 보유 검증용입니다. 짧은 창(30~90일)은 참고용 스윙 검증입니다." />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ color: "var(--text-muted)" }}>
                <th className="text-left py-1.5 font-semibold">비교 대상</th>
                {HORIZONS.map((h) => (
                  <th key={h} className="text-right py-1.5 font-semibold whitespace-nowrap">{HORIZON_LABEL[h]} 후</th>
                ))}
                <th className="text-right py-1.5 font-semibold">표본수</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map(({ key, label, desc }) => {
                const b = data.comparison[key];
                return (
                  <tr key={key} style={{ borderTop: "1px solid var(--border)" }}>
                    <td className="py-2 pr-3">
                      <div className="font-semibold whitespace-nowrap" style={{ color: "var(--text-primary)" }}>{label}</div>
                      <div className="text-[11px]" style={{ color: "var(--text-faint)" }}>{desc}</div>
                    </td>
                    {HORIZONS.map((h) => {
                      const v = b[`fwd_${h}d_ret`];
                      return (
                        <td key={h} className="text-right font-mono font-bold" style={{ color: pctColor(v) }}>{pct(v)}</td>
                      );
                    })}
                    <td className="text-right font-mono" style={{ color: "var(--text-faint)" }}>{b.n}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 기간 선택 — 등급별/게이트별 카드에 공통 적용 */}
      <div className="bg-card rounded-xl p-3 flex items-center gap-2">
        <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>등급·게이트별 기준 기간</span>
        <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          {HORIZONS.map((h) => (
            <button
              key={h}
              onClick={() => setBreakdownHorizon(h)}
              className="px-2.5 py-1 text-[11px] font-semibold transition-colors"
              style={{
                background: breakdownHorizon === h ? "#ffb02022" : "transparent",
                color: breakdownHorizon === h ? "#ffb020" : "var(--text-faint)",
              }}
            >
              {HORIZON_LABEL[h]}
            </button>
          ))}
        </div>
      </div>

      {/* Piotroski 구간별 */}
      <div className="bg-card rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <h2 className="stat-label">Piotroski 구간별 이후 {HORIZON_LABEL[breakdownHorizon]} 수익률</h2>
          <InfoTooltip content="스크리닝 시점 Piotroski F-Score 구간이 실제 수익률 순서와 대응하는지 확인합니다. 점수가 높을수록 수익률도 높다면 필터가 실제로 값을 더하고 있다는 뜻입니다." />
        </div>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(data.by_piotroski).map(([tier, b]) => (
            <div key={tier} className="rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <p className="text-[13px] font-black" style={{ color: "var(--text-primary)" }}>{tier}</p>
              <p className="text-[16px] font-black font-mono mt-1" style={{ color: pctColor(b[bdCol]) }}>{pct(b[bdCol])}</p>
              <p className="text-[11px] mt-0.5" style={{ color: "var(--text-faint)" }}>n={b.n}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
