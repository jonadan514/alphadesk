"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";
import MiniPortfolio from "@/src/components/MiniPortfolio";

const VERDICT_COLOR: Record<string, string> = {
  GO:      "#39ff8f",
  CAUTION: "#facc15",
  STOP:    "#ef4444",
};

const US_SENSOR_LABEL: Record<string, string> = {
  vix: "VIX", trend: "TREND", breadth: "BREADTH",
  credit: "CREDIT", yield_curve: "YIELD CURVE", put_call: "PUT/CALL",
};

const KR_SENSOR_LABEL: Record<string, string> = {
  trend: "TREND", volatility: "VOLATILITY", momentum: "MOMENTUM", breadth: "BREADTH",
};

function KpiCard({ label, value, sub, color, tooltip }: {
  label: string; value: string; sub?: string; color?: string; tooltip: string;
}) {
  return (
    <div className="bg-card rounded-xl p-3 flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5">
        <p className="stat-label">{label}</p>
        <InfoTooltip content={tooltip} />
      </div>
      <p className="text-3xl font-black leading-none" style={{ color: color ?? "var(--text-primary)" }}>{value}</p>
      {sub && <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>{sub}</p>}
    </div>
  );
}

function sensorInfo(score: number, isKR: boolean) {
  if (isKR) {
    if (score >= 1.5) return { text: "강세", color: "#39ff8f" };
    if (score >= 0.5) return { text: "중립", color: "#facc15" };
    if (score >= 0)   return { text: "약세", color: "#f97316" };
    return { text: "위기", color: "#ef4444" };
  }
  if (score <= 0.5) return { text: "위험 선호", color: "#39ff8f" };
  if (score <= 1.0) return { text: "중립",     color: "#facc15" };
  if (score <= 2.0) return { text: "주의",     color: "#f97316" };
  return { text: "위험 회피", color: "#ef4444" };
}

export default function HomePage() {
  const { market } = useMarket();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    setData(null);
    if (market === "KR") {
      Promise.allSettled([
        fetch("/api/data/kr/market-gate").then(r => r.json()),
        fetch("/api/data/kr/regime").then(r => r.json()),
        fetch("/api/data/kr/reports?limit=1").then(r => r.json()),
      ]).then(([gateRes, regimeRes, reportsRes]) => {
        setData({
          gate:    gateRes.status    === "fulfilled" ? gateRes.value    : {},
          regime:  regimeRes.status  === "fulfilled" ? regimeRes.value  : {},
          report:  reportsRes.status === "fulfilled" ? (reportsRes.value[0] ?? {}) : {},
          prediction: null,
        });
      });
    } else {
      Promise.allSettled([
        fetch("/api/data/market-gate").then(r => r.json()),
        fetch("/api/data/regime").then(r => r.json()),
        fetch("/api/data/index-prediction").then(r => r.json()),
        fetch("/api/data/reports?limit=1").then(r => r.json()),
      ]).then(([gateRes, regimeRes, predRes, reportsRes]) => {
        setData({
          gate:       gateRes.status    === "fulfilled" ? gateRes.value    : {},
          regime:     regimeRes.status  === "fulfilled" ? regimeRes.value  : {},
          prediction: predRes.status    === "fulfilled" ? predRes.value    : {},
          report:     reportsRes.status === "fulfilled" ? (reportsRes.value[0] ?? {}) : {},
        });
      });
    }
  }, [market]);

  if (!data) return (
    <div className="space-y-3">
      <div className="h-32 rounded-xl animate-pulse" style={{ background: "#1c1c1c" }} />
    </div>
  );

  const isKR = market === "KR";
  const { gate, regime, prediction, report } = data;
  const picks: any[] = report.picks ?? [];
  const top5 = picks.slice(0, 5);
  const spy = prediction?.spy ?? (prediction?.direction ? prediction : null);
  const verdict = report.verdict ?? gate.gate ?? "—";
  const verdictColor = VERDICT_COLOR[verdict] ?? "#fff";
  const sensors: Record<string, number> = regime.sensor_scores ?? {};
  const sensorLabel = isKR ? KR_SENSOR_LABEL : US_SENSOR_LABEL;
  const indexName = isKR ? "KOSPI" : "S&P 500";

  // ── 모바일 요약 뷰 ──────────────────────────────────────
  const MobileView = () => (
    <div className="md:hidden space-y-3 pb-6">
      {/* 내 포트폴리오 */}
      <MiniPortfolio />

      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FlagIcon market={isKR ? "KR" : "US"} size={16} />
          <span className="text-sm font-bold text-white">{isKR ? "한국 주식" : "미국 주식"}</span>
        </div>
        <span className="rounded px-2 py-0.5 text-[11px] font-bold" style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
          LIVE
        </span>
      </div>

      {/* 종합 판단 */}
      <div
        className="rounded-xl p-5 flex flex-col items-center gap-1 text-center"
        style={{
          background: verdict === "GO" ? "#39ff8f18" : verdict === "CAUTION" ? "#facc1518" : "#ef444418",
          border: `1px solid ${verdictColor}44`,
        }}
      >
        <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: verdictColor }}>종합 판단</p>
        <p className="text-5xl font-black" style={{ color: verdictColor }}>{verdict}</p>
        <p className="text-[12px] mt-1" style={{ color: "#9ca3af" }}>
          {verdict === "GO" ? "진입 가능" : verdict === "CAUTION" ? "경계 — 신중하게" : verdict === "STOP" ? "신규 진입 자제" : "—"}
        </p>
      </div>

      {/* 핵심 지표 3개 */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "체제 점수", value: regime.weighted_score != null ? regime.weighted_score.toFixed(2) : "—", sub: regime.regime_label ?? regime.regime ?? "—", color: "#39ff8f" },
          { label: "스크리닝", value: String(picks.length), sub: isKR ? "KOSPI 종목" : "S&P 종목", color: "#fff" },
          { label: "마켓 게이트", value: gate.gate ?? "—", sub: isKR ? (gate.reason ?? "") : `avg ${gate.avg_score?.toFixed(1) ?? "—"}`, color: VERDICT_COLOR[gate.gate] ?? "#fff" },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="rounded-xl p-3 flex flex-col gap-1" style={{ background: "var(--bg-card)" }}>
            <p className="text-[10px] uppercase tracking-wide" style={{ color: "#6b7280" }}>{label}</p>
            <p className="text-xl font-black leading-none" style={{ color }}>{value}</p>
            <p className="text-[10px] truncate" style={{ color: "#6b7280" }}>{sub}</p>
          </div>
        ))}
      </div>

      {/* SPY / KOSPI 예측 */}
      {!isKR && spy && (
        <div className="rounded-xl p-3 flex items-center justify-between" style={{ background: "var(--bg-card)" }}>
          <div>
            <p className="text-[11px] uppercase tracking-wide mb-1" style={{ color: "#6b7280" }}>SPY 예측</p>
            <p className="text-lg font-black" style={{ color: spy.direction === "bullish" ? "#39ff8f" : "#ef4444" }}>
              {spy.direction === "bullish" ? "강세" : "약세"}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[11px]" style={{ color: "#6b7280" }}>확률</p>
            <p className="text-lg font-bold text-white">
              {spy.probability != null ? `${Math.round(spy.probability * 100)}%` : "—"}
            </p>
          </div>
        </div>
      )}

      {/* 상위 픽 */}
      {top5.length > 0 && (
        <div className="rounded-xl p-3" style={{ background: "var(--bg-card)" }}>
          <p className="text-[11px] uppercase tracking-wide mb-2" style={{ color: "#6b7280" }}>
            상위 {isKR ? "KOSPI" : "알파"} 픽
          </p>
          <div className="space-y-2">
            {top5.map((p: any) => (
              <div key={p.symbol} className="flex items-center gap-2">
                <span className="w-5 h-5 rounded text-[10px] font-black flex items-center justify-center shrink-0"
                  style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
                  {p.grade}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-bold text-white truncate block">{p.name ?? p.symbol}</span>
                  {p.name && <span className="text-[10px] font-mono" style={{ color: "#6b7280" }}>{p.symbol}</span>}
                </div>
                <span className="text-sm font-bold shrink-0" style={{ color: "#39ff8f" }}>{p.composite_score?.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {picks.length === 0 && Object.keys(sensors).length === 0 && (
        <div className="rounded-xl p-4 text-center text-sm" style={{ background: "var(--bg-card)", color: "#6b7280" }}>
          데이터 없음. 분석 실행 후 재확인하세요.
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-3">
      <MobileView />

      {/* 데스크톱 전용 ─────────────────────────────────── */}
      <div className="hidden md:block space-y-3">

      {/* Title */}
      <div className="flex items-center gap-3">
        <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
          <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
        </span>
        <h1 className="text-xl font-bold text-white">
          {isKR ? "한국 주식 마켓 인텔리전스" : "미국 주식 마켓 인텔리전스"}
        </h1>
        <span className="rounded px-2 py-0.5 text-[12px] font-bold" style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
          LIVE
        </span>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard
          label="종합 판단"
          value={verdict}
          sub={verdict === "GO" ? "진입 가능" : verdict === "CAUTION" ? "경계 — 신중하게" : verdict === "STOP" ? "신규 진입 자제" : "—"}
          color={verdictColor}
          tooltip="시장 체제·게이트·스크리닝 결과를 종합한 최종 판단입니다."
        />
        <KpiCard
          label="체제 점수"
          value={regime.weighted_score != null ? regime.weighted_score.toFixed(2) : "—"}
          sub={regime.regime_label ?? regime.regime ?? "—"}
          color="#39ff8f"
          tooltip={isKR
            ? "KOSPI 4개 센서(추세·변동성·모멘텀·브레드스) 가중 합산 점수입니다. 높을수록 강세."
            : "5개 센서(VIX·Trend·Breadth·Credit·YieldCurve) 가중합. 낮을수록 risk_on."}
        />
        <KpiCard
          label="스크리닝"
          value={String(picks.length)}
          sub={isKR ? "KOSPI 4팩터 상위 종목" : "6-factor 복합 점수 상위"}
          tooltip={isKR
            ? "기술·펀더멘털·KOSPI 대비 RS·거래량 4팩터 스크리닝 결과입니다."
            : "6-factor 복합 점수로 S&P 500 전 종목 분석 결과입니다."}
        />
        <KpiCard
          label="마켓 게이트"
          value={gate.gate ?? "—"}
          sub={isKR
            ? (gate.reason ?? "")
            : `평균 점수 ${gate.avg_score?.toFixed(2) ?? "—"}`}
          color={VERDICT_COLOR[gate.gate] ?? "#fff"}
          tooltip="시장 진입 최종 필터입니다. GO = 진입 가능, CAUTION = 경계, STOP = 진입 자제."
        />
      </div>

      <div className="grid grid-cols-3 gap-3">
        {/* Left: sensors + picks */}
        <div className="col-span-2 space-y-3">
          {/* Sensors */}
          {Object.keys(sensors).length > 0 && (
            <div className="bg-card rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <h2 className="stat-label">핵심 체제 지표</h2>
                <InfoTooltip content="각 센서는 독립적으로 시장 국면을 측정합니다." />
              </div>
              {(() => {
                const entries = Object.entries(sensors);
                const cols = entries.length <= 4 ? entries.length : entries.length <= 6 ? 3 : 4;
                return (
                  <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
                    {entries.map(([key, val]) => {
                      const info = sensorInfo(val, isKR);
                      return (
                        <div key={key} className="rounded-xl p-3" style={{ background: "var(--bg-inset)", border: `1px solid ${info.color}33` }}>
                          <p className="text-[12px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>
                            {sensorLabel[key] ?? key}
                          </p>
                          <p className="text-sm font-bold" style={{ color: info.color }}>{info.text}</p>
                          <p className="text-[12px] font-mono mt-0.5" style={{ color: "var(--text-faint)" }}>{val.toFixed(2)}</p>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          )}

          {/* KR: additional metrics */}
          {isKR && regime.kospi_last && (
            <div className="bg-card rounded-lg p-3">
              <h2 className="stat-label mb-2">KOSPI 주요 지표</h2>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: "KOSPI", val: regime.kospi_last?.toLocaleString(), color: "var(--text-primary)" },
                  { label: "SMA 200", val: regime.kospi_sma200?.toLocaleString(), color: "#6e6e6e" },
                  { label: "변동성(60일)", val: `${regime.vol_60d?.toFixed(1)}%`, color: regime.vol_60d > 25 ? "#ef4444" : "#facc15" },
                  { label: "모멘텀(20일)", val: regime.mom_20d != null ? `${regime.mom_20d >= 0 ? "+" : ""}${regime.mom_20d.toFixed(1)}%` : "—", color: regime.mom_20d != null ? (regime.mom_20d >= 0 ? "#39ff8f" : "#ef4444") : "var(--text-muted)" },
                ].map(({ label, val, color }) => (
                  <div key={label} className="rounded-lg p-3 text-center" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
                    <p className="text-[12px] mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
                    <p className="text-base font-bold" style={{ color }}>{val ?? "—"}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top picks */}
          {top5.length > 0 && (
            <div className="bg-card rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <h2 className="stat-label">상위 5 {isKR ? "KOSPI" : "알파"} 픽</h2>
                  <InfoTooltip content="복합 점수 상위 5개 종목입니다." />
                </div>
              </div>
              <div className="space-y-2">
                {top5.map((p: any) => (
                  <div key={p.symbol} className="flex items-center gap-3 py-2 border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                    <span className="w-6 h-6 rounded flex items-center justify-center text-[12px] font-black" style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
                      {p.grade}
                    </span>
                    <div className="flex-1 min-w-0">
                      {p.name
                        ? <><span className="text-sm font-bold text-white">{p.name}</span>
                            <span className="ml-2 text-[12px] font-mono" style={{ color: "var(--text-muted)" }}>{p.symbol}</span></>
                        : <span className="text-sm font-bold text-white">{p.symbol}</span>
                      }
                      {p.sector && <span className="ml-2 text-[12px]" style={{ color: "var(--text-faint)" }}>{p.sector}</span>}
                    </div>
                    <span className="text-sm font-bold" style={{ color: "#39ff8f" }}>{p.composite_score?.toFixed(1)}</span>
                    <span className="text-[12px] px-2 py-0.5 rounded" style={{ background: "#202020", color: "var(--text-secondary)" }}>{p.action}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!data || (picks.length === 0 && Object.keys(sensors).length === 0) && (
            <div className="bg-card rounded-lg p-3 text-center text-sm text-[#6b7280]">
              데이터 없음. {isKR ? "python scripts/run_kr_analysis.py" : "alpharun"} 실행 후 재확인하세요.
            </div>
          )}
        </div>

        {/* Right */}
        <div className="space-y-3">
          {/* Verdict card */}
          <div
            className="rounded-lg p-5 flex flex-col items-center justify-center gap-2 text-center"
            style={{
              background: verdict === "GO" ? "#39ff8f18" : verdict === "CAUTION" ? "#facc1518" : "#ef444418",
              border: `1px solid ${verdictColor}44`,
            }}
          >
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-bold uppercase tracking-widest" style={{ color: verdictColor }}>종합 판단</span>
            </div>
            <p className="text-4xl font-black" style={{ color: verdictColor }}>{verdict}</p>
            <p className="text-[12px] text-[#6b7280]">
              체제: <span className="text-white font-semibold">{regime.regime?.replace("_", " ") ?? "—"}</span>
              &nbsp;·&nbsp;점수: <span className="text-white font-semibold">{regime.weighted_score?.toFixed(2) ?? "—"}</span>
            </p>
            {isKR && gate.reason && (
              <p className="text-[12px] text-[#9ca3af] text-center px-2">{gate.reason}</p>
            )}
          </div>

          {/* US: SPY 예측 */}
          {!isKR && spy && (
            <div className="bg-card rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <h2 className="stat-label">SPY 예측</h2>
                <InfoTooltip content="LightGBM 모델의 다음 주 SPY 방향 예측입니다." />
              </div>
              <p className="text-2xl font-black mb-1" style={{ color: spy.direction === "bullish" ? "#39ff8f" : "#ef4444" }}>
                {spy.direction === "bullish" ? "강세" : "약세"}
              </p>
              <p className="text-sm font-semibold text-white">
                확률 {spy.probability != null ? `${Math.round(spy.probability * 100)}%` : "—"}
              </p>
              {spy.cv_accuracy != null && (
                <p className="text-[12px] mt-1" style={{ color: "var(--text-muted)" }}>
                  모델 정확도 {Math.round(spy.cv_accuracy * 100)}%
                </p>
              )}
            </div>
          )}

          {/* KR: KOSPI 예측 요약 */}
          {isKR && (
            <div className="bg-card rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <h2 className="stat-label">KOSPI 방향성</h2>
              </div>
              <p className="text-sm font-bold text-[#6b7280] mb-2">체제 기반 방향 추정</p>
              {regime.mom_20d != null && (
                <>
                  <p className="text-2xl font-black mb-1" style={{ color: regime.mom_20d >= 0 ? "#39ff8f" : "#ef4444" }}>
                    {regime.mom_20d >= 0 ? "상승 모멘텀" : "하락 모멘텀"}
                  </p>
                  <p className="text-sm text-[#6b7280]">20일: {regime.mom_20d >= 0 ? "+" : ""}{regime.mom_20d?.toFixed(2)}%</p>
                </>
              )}
              <p className="text-[12px] mt-2" style={{ color: "var(--text-muted)" }}>
                ※ 지수 예측 탭에서 상세 분석 확인
              </p>
            </div>
          )}

          {/* Mini portfolio */}
          <MiniPortfolio />
        </div>
      </div>

      </div> {/* end hidden md:block */}
    </div>
  );
}
