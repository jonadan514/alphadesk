"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";

const CYCLE_COLOR: Record<string, string> = {
  early:     "#60a5fa",
  mid:       "#39ff8f",
  late:      "#facc15",
  recession: "#ef4444",
};

const CYCLE_KO: Record<string, { label: string; desc: string }> = {
  early:     { label: "회복기 (Early)",     desc: "경기 바닥 이후 반등. 금융·부동산·소비재 강세" },
  mid:       { label: "성장기 (Mid)",       desc: "확장 지속. IT·산업재·소재 강세" },
  late:      { label: "과열기 (Late)",      desc: "성장 둔화 시작. 에너지·원자재·헬스케어 강세" },
  recession: { label: "침체기 (Recession)", desc: "수요 위축. 유틸리티·필수소비재·채권 강세" },
};

const PERIOD_TABS = ["1d", "1w", "1m", "3m"] as const;
type Period = typeof PERIOD_TABS[number];

function pct(v: number | null | undefined, digits = 2) {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

function RetCell({ val }: { val: number | null | undefined }) {
  if (val == null) return <td className="px-2 py-1.5 text-center" style={{ color: "var(--text-faint)" }}>—</td>;
  const color = val > 0 ? "#39ff8f" : val < 0 ? "#ef4444" : "var(--text-muted)";
  return (
    <td className="px-2 py-1.5 text-center font-semibold text-[12px]" style={{ color }}>
      {pct(val)}
    </td>
  );
}

export default function SectorPage() {
  const { market } = useMarket();
  const [data, setData]       = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod]   = useState<Period>("1w");
  const [openKey, setOpenKey] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setData(null);
    const url = market === "KR" ? "/api/data/kr/sector" : "/api/data/sector";
    fetch(url).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, [market]);

  if (loading) return <p className="text-sm" style={{ color: "var(--text-muted)" }}>로딩 중…</p>;

  if (!data) return (
    <div className="space-y-2">
      <h1 className="text-base font-bold text-white">섹터 분석</h1>
      <div className="bg-card rounded-xl p-3">
        <p className="text-sm font-semibold text-white mb-1">데이터가 없습니다</p>
        <p className="text-[12px] mb-2" style={{ color: "var(--text-muted)" }}>
          {market === "KR" ? "python scripts/run_kr_analysis.py" : "alpharun"} 실행 후 자동으로 계산됩니다.
        </p>
        <code className="block text-[12px] rounded-lg px-3 py-2" style={{ background: "var(--bg-inset)", color: "#39ff8f" }}>
          {market === "KR" ? "python scripts/run_kr_analysis.py" : "alpharun"}
        </code>
      </div>
    </div>
  );

  const isKR = market === "KR";
  const cycle       = data.current_cycle ?? "mid";
  const cycleLabel  = CYCLE_KO[cycle]?.label ?? data.cycle_label ?? "Mid Cycle";
  const cycleColor  = CYCLE_COLOR[cycle] ?? "#39ff8f";
  const scores      = data.cycle_scores ?? {};

  const rows: any[]       = isKR ? (data.sector_data ?? []) : (data.etf_data ?? []);
  const rsHistory: any[]  = data.rs_history ?? [];
  const sectorStocks: Record<string, any[]> = data.sector_stocks ?? {};
  const leading: any[]    = data.leading ?? [];
  const lagging: any[]    = data.lagging ?? [];
  const benchmarkRet      = isKR ? data.kospi_ret : data.spy_ret;

  const maxAbsScore = Math.max(...(Object.values(scores) as number[]).map(Math.abs), 1);

  function rowKey(row: any) { return isKR ? row.sector : row.ticker; }
  function rowLabel(row: any) { return isKR ? row.sector : row.ticker; }
  function rowSubLabel(row: any) { return isKR ? "" : row.name; }

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
          <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
        </span>
        <h1 className="text-base font-bold text-white">섹터 분석</h1>
        <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>{data.date}</span>
        <InfoTooltip content={isKR ? "KOSPI 섹터별 앵커 종목 기반 상대강도 분석입니다." : "11개 SPDR ETF 기반 섹터 순환 분석입니다. SPY 대비 상대 강도(RS)로 경기 사이클을 판단합니다."} />
      </div>

      {/* 경기 사이클 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">

        {/* 사이클 판단 */}
        <div className="bg-card rounded-xl p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <p className="text-[14px] font-bold text-white">경기 사이클 판단</p>
            <InfoTooltip content="각 섹터 ETF의 최근 상대강도(RS)를 종합해 현재 경기가 어느 단계인지 자동 판별합니다. 사이클 단계별로 강세를 보이는 섹터가 다릅니다." />
          </div>
          <p className="text-[11px] mb-2" style={{ color: "var(--text-faint)" }}>
            {CYCLE_KO[cycle]?.desc ?? ""}
          </p>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">→</span>
            <p className="text-[22px] font-black leading-none" style={{ color: cycleColor }}>{cycleLabel}</p>
          </div>
          <div className="space-y-1.5">
            {Object.entries(scores).map(([cyc, val]: any) => {
              const isActive = cyc === cycle;
              const barW = Math.round((Math.abs(val) / maxAbsScore) * 100);
              const c = CYCLE_COLOR[cyc] ?? "#9ca3af";
              return (
                <div key={cyc}>
                  <div className="flex justify-between text-[12px] mb-0.5">
                    <span style={{ color: isActive ? c : "var(--text-muted)", fontWeight: isActive ? 700 : 400 }}>
                      {CYCLE_KO[cyc]?.label ?? cyc.toUpperCase()}
                    </span>
                    <span style={{ color: val > 0 ? "#39ff8f" : "#ef4444" }}>{pct(val)}</span>
                  </div>
                  <div className="h-1 rounded-full" style={{ background: "var(--bg-inset)" }}>
                    <div className="h-1 rounded-full" style={{ width: `${barW}%`, background: isActive ? c : "#444" }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 국면별 점수 */}
        <div className="bg-card rounded-xl p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <p className="text-[14px] font-bold text-white">국면별 점수</p>
            <InfoTooltip content="각 경기 국면에 해당하는 섹터들의 상대강도 평균입니다. 점수가 높을수록 해당 국면의 섹터들이 시장을 아웃퍼폼 중입니다." />
          </div>
          <p className="text-[11px] mb-2" style={{ color: "var(--text-faint)" }}>점수가 높은 국면 = 현재 강세를 보이는 섹터 그룹</p>
          <div className="grid grid-cols-2 gap-2">
            {(["early", "mid", "late", "recession"] as const).map(cyc => {
              const score = scores[cyc] ?? 0;
              const c = CYCLE_COLOR[cyc];
              const isActive = cyc === cycle;
              return (
                <div key={cyc} className="rounded-lg p-2.5 text-center"
                  style={{
                    background: isActive ? `${c}12` : "var(--bg-inset)",
                    border: `1px solid ${isActive ? c + "44" : "var(--border)"}`,
                  }}>
                  <p className="text-[11px] mb-0.5" style={{ color: isActive ? c : "var(--text-muted)" }}>
                    {CYCLE_KO[cyc]?.label ?? cyc}
                  </p>
                  <p className="text-[18px] font-black leading-none" style={{ color: score > 0 ? "#39ff8f" : "#ef4444" }}>
                    {pct(score)}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* 선행 / 후행 섹터 */}
        <div className="bg-card rounded-xl p-3 space-y-2">
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <p className="text-[13px] font-bold" style={{ color: "#39ff8f" }}>↑ 선행 섹터</p>
              <InfoTooltip content="최근 4주간 시장 대비 상대강도(RS)가 지속적으로 강한 섹터입니다. 자금이 집중되고 있는 섹터로, 포트폴리오 편입 우선순위가 높습니다." />
            </div>
            <div className="flex flex-wrap gap-1">
              {leading.map((l: any, i: number) => (
                <span key={isKR ? (l.sector ?? i) : (l.ticker ?? i)} className="text-[12px] font-bold px-2 py-0.5 rounded-lg"
                  style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
                  {isKR ? l.sector : `${l.ticker} · ${l.name}`}
                </span>
              ))}
              {leading.length === 0 && <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>없음</p>}
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <p className="text-[13px] font-bold" style={{ color: "#ef4444" }}>↓ 후행 섹터</p>
              <InfoTooltip content="최근 4주간 시장 대비 상대강도(RS)가 지속적으로 약한 섹터입니다. 자금이 빠지고 있는 섹터로, 비중 축소를 고려할 수 있습니다." />
            </div>
            <div className="flex flex-wrap gap-1">
              {lagging.map((l: any, i: number) => (
                <span key={isKR ? (l.sector ?? i) : (l.ticker ?? i)} className="text-[12px] font-bold px-2 py-0.5 rounded-lg"
                  style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444433" }}>
                  {isKR ? l.sector : `${l.ticker} · ${l.name}`}
                </span>
              ))}
              {lagging.length === 0 && <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>없음</p>}
            </div>
          </div>
        </div>
      </div>

      {/* RS History */}
      <div className="bg-card rounded-xl overflow-hidden">
        <div className="px-3 py-2 flex items-center gap-2" style={{ borderBottom: "1px solid var(--border)" }}>
          <p className="text-[14px] font-bold text-white">주간 상대강도 추이 <span className="text-[12px] font-normal" style={{ color: "var(--text-muted)" }}>(최근 4주)</span></p>
          <InfoTooltip content={`${isKR ? "KOSPI" : "SPY"} 대비 초과 수익률입니다. 양수(+)면 시장보다 더 올랐고, 음수(-)면 시장보다 덜 올랐다는 의미입니다. 여러 주에 걸쳐 양수를 유지하면 선행 섹터로 분류됩니다.`} />
        </div>
        <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="px-3 py-1.5 text-left stat-label w-36">섹터</th>
              {["이번주", "1주전", "2주전", "3주전"].map(h => (
                <th key={h} className="px-2 py-1.5 text-center stat-label">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rsHistory.map((row: any, i: number) => (
              <tr key={isKR ? (row.sector ?? i) : (row.ticker ?? i)} style={{ borderBottom: "1px solid var(--border-dim)" }}>
                <td className="px-3 py-1.5">
                  {isKR ? (
                    <span className="text-white text-[12px] font-semibold">{row.sector}</span>
                  ) : (
                    <>
                      <span className="font-bold text-white">{row.ticker}</span>
                      <span className="ml-1 text-[11px]" style={{ color: "var(--text-muted)" }}>{row.name}</span>
                    </>
                  )}
                </td>
                <RetCell val={row.w0} />
                <RetCell val={row.w1} />
                <RetCell val={row.w2} />
                <RetCell val={row.w3} />
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* 섹터 히트맵 */}
      <div className="bg-card rounded-xl overflow-hidden">
        <div className="px-3 py-2 flex items-center gap-2" style={{ borderBottom: "1px solid var(--border)" }}>
          <p className="text-[14px] font-bold text-white">섹터별 수익률 · 상대강도</p>
          <InfoTooltip content="왼쪽 수치(%)는 해당 기간 절대 수익률, 오른쪽 바와 수치는 시장(SPY/KOSPI) 대비 상대강도(RS)입니다. RS가 양수이면 시장을 이기고 있다는 의미입니다. 섹터를 클릭하면 포함된 종목을 볼 수 있습니다." />
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>기간 선택</span>
            <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
              {PERIOD_TABS.map(p => (
                <button key={p} onClick={() => setPeriod(p)}
                  className="px-2.5 py-1 text-[12px] font-semibold transition-colors"
                  style={{
                    background: period === p ? "#39ff8f18" : "transparent",
                    color: period === p ? "#39ff8f" : "var(--text-muted)",
                  }}>
                  {p === "1d" ? "1일" : p === "1w" ? "1주" : p === "1m" ? "1달" : "3달"}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 컬럼 헤더 */}
        <div className="flex items-center gap-3 px-3 py-1" style={{ borderBottom: "1px solid var(--border-dim)", background: "var(--bg-inset)" }}>
          <span className="w-32 text-[11px] font-semibold" style={{ color: "var(--text-faint)" }}>섹터</span>
          {!isKR && <span className="w-28 text-[11px]" style={{ color: "var(--text-faint)" }}>이름</span>}
          {!isKR && <span className="w-16 text-[11px]" style={{ color: "var(--text-faint)" }}>현재가</span>}
          <span className="w-16 text-[11px]" style={{ color: "var(--text-faint)" }}>수익률</span>
          <span className="flex-1 text-[11px]" style={{ color: "var(--text-faint)" }}>시장 대비 상대강도 (RS) — 중앙 기준, 우측=아웃퍼폼</span>
        </div>

        <div className="divide-y" style={{ borderColor: "var(--border-dim)" }}>
          {(() => {
            const maxAbsRS = Math.max(...rows.map((r: any) => Math.abs(r[`rs_${period}`] ?? 0)), 1);
            return rows.map((row: any) => {
            const key    = rowKey(row);
            const ret    = row[`ret_${period}`];
            const rs     = row[`rs_${period}`];
            const stocks = sectorStocks[key] ?? [];
            const isOpen = openKey === key;
            const barPct = rs != null ? Math.min((Math.abs(rs) / maxAbsRS) * 50, 50) : 0;

            return (
              <div key={key}>
                <button
                  onClick={() => setOpenKey(isOpen ? null : key)}
                  className="w-full flex items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-white/5"
                >
                  <span className="w-32 font-bold text-white text-[12px] truncate">{rowLabel(row)}</span>
                  {rowSubLabel(row) && (
                    <span className="w-28 text-[12px] truncate" style={{ color: "var(--text-secondary)" }}>{rowSubLabel(row)}</span>
                  )}

                  {!isKR && (
                    <span className="w-16 text-[12px]" style={{ color: "var(--text-muted)" }}>
                      ${row.cur_price?.toFixed(2) ?? "—"}
                    </span>
                  )}

                  <span className="w-16 text-[12px] font-bold" style={{ color: ret == null ? "var(--text-muted)" : ret >= 0 ? "#39ff8f" : "#ef4444" }}>
                    {pct(ret)}
                  </span>

                  <div className="flex-1 flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full relative" style={{ background: "var(--bg-inset)" }}>
                      {rs != null && (
                        <div className="absolute top-0 h-1.5 rounded-full"
                          style={{
                            width: `${barPct}%`,
                            left: rs >= 0 ? "50%" : `${50 - barPct}%`,
                            background: rs >= 0 ? "#39ff8f" : "#ef4444",
                          }} />
                      )}
                    </div>
                    <span className="w-14 text-right text-[12px] font-semibold"
                      style={{ color: rs == null ? "var(--text-muted)" : rs >= 0 ? "#39ff8f" : "#ef4444" }}>
                      {pct(rs)}
                    </span>
                  </div>

                  <span className="text-[11px] w-14 text-right" style={{ color: "var(--text-muted)" }}>
                    {stocks.length > 0 ? `${stocks.length}종목` : ""}
                    {" "}{isOpen ? "▲" : "▼"}
                  </span>
                </button>

                {isOpen && stocks.length > 0 && (
                  <div className="px-3 pb-2" style={{ borderTop: "1px solid var(--border-dim)" }}>
                    <div className="flex flex-wrap gap-1.5 pt-2">
                      {stocks.map((s: any) => (
                        <div key={s.symbol} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[12px]"
                          style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
                          <span className="font-bold text-white">{s.symbol}</span>
                          {isKR && s.name && <span style={{ color: "#a8a8a8" }}>{s.name}</span>}
                          <span className="px-1 rounded text-[12px] font-bold badge-go">{s.grade}</span>
                          {s.score != null && (
                            <span style={{ color: "var(--text-muted)" }}>{s.score.toFixed(0)}점</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          });
          })()}
        </div>
      </div>

      {benchmarkRet && (
        <div className="rounded-xl px-3 py-2 text-[12px] flex items-center gap-2 flex-wrap" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
          <span className="font-bold" style={{ color: "var(--text-muted)" }}>
            {isKR ? "KOSPI" : "SPY"} 벤치마크 수익률
          </span>
          {Object.entries(benchmarkRet).map(([label, val]: any) => (
            <span key={label} className="font-semibold" style={{ color: val >= 0 ? "#39ff8f" : "#ef4444" }}>
              {label}: {pct(val)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
