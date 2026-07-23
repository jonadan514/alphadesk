"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";
import MiniPortfolio from "@/src/components/MiniPortfolio";

const VERDICT_COLOR: Record<string, string> = {
  GO:      "#4ade80",
  CAUTION: "#facc15",
  STOP:    "#f87171",
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
        <p className="stat-label" style={{ fontSize: 13 }}>{label}</p>
        <InfoTooltip content={tooltip} />
      </div>
      <p className="text-4xl font-black leading-none" style={{ color: color ?? "var(--text-primary)" }}>{value}</p>
      {sub && <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>{sub}</p>}
    </div>
  );
}

function sensorInfo(score: number, isKR: boolean) {
  if (isKR) {
    if (score >= 1.5) return { text: "강세", color: "#4ade80" };
    if (score >= 0.5) return { text: "중립", color: "#facc15" };
    if (score >= 0)   return { text: "약세", color: "#fb923c" };
    return { text: "위기", color: "#f87171" };
  }
  if (score <= 0.5) return { text: "위험 선호", color: "#4ade80" };
  if (score <= 1.0) return { text: "중립",     color: "#facc15" };
  if (score <= 2.0) return { text: "주의",     color: "#fb923c" };
  return { text: "위험 회피", color: "#f87171" };
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
        fetch("/api/data/kr/forecast").then(r => r.json()),
      ]).then(([gateRes, regimeRes, reportsRes, predRes]) => {
        setData({
          gate:    gateRes.status    === "fulfilled" ? gateRes.value    : {},
          regime:  regimeRes.status  === "fulfilled" ? regimeRes.value  : {},
          report:  reportsRes.status === "fulfilled" ? (reportsRes.value[0] ?? {}) : {},
          prediction: predRes.status === "fulfilled" ? predRes.value : null,
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
      <div className="h-32 rounded-xl animate-pulse" style={{ background: "#111009" }} />
    </div>
  );

  const isKR = market === "KR";
  const { gate, regime, prediction, report } = data;
  const picks: any[] = report.picks ?? [];
  const top5 = picks.slice(0, 5);
  const spy = prediction?.spy ?? (prediction?.direction ? prediction : null);
  const predTitle = isKR ? "KOSPI 예측" : "SPY 예측";
  const dirInfo = (d?: string) =>
    d === "bullish" ? { text: "강세", color: "#4ade80" } :
    d === "bearish" ? { text: "약세", color: "#f87171" } :
    { text: "중립", color: "#facc15" };
  const verdict = report.verdict ?? gate.gate ?? "—";
  const verdictColor = VERDICT_COLOR[verdict] ?? "#ece7d8";
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
          <span className="text-base font-bold text-white">{isKR ? "한국 주식" : "미국 주식"}</span>
        </div>
        <span className="rounded px-2 py-0.5 text-[12px] font-bold" style={{ background: "#ffb02022", color: "#ffb020", border: "1px solid #ffb02044" }}>
          LIVE
        </span>
      </div>

      {/* 종합 판단 */}
      <div
        className="rounded-xl p-5 flex flex-col items-center gap-1 text-center"
        style={{
          background: verdict === "GO" ? "#4ade8018" : verdict === "CAUTION" ? "#facc1518" : "#f8717118",
          border: `1px solid ${verdictColor}44`,
        }}
      >
        <p className="text-[12px] font-semibold uppercase tracking-widest" style={{ color: verdictColor }}>종합 판단</p>
        <p className="text-6xl font-black" style={{ color: verdictColor }}>{verdict}</p>
        <p className="text-[13px] mt-1" style={{ color: "#a39c88" }}>
          {verdict === "GO" ? "진입 가능" : verdict === "CAUTION" ? "경계 — 신중하게" : verdict === "STOP" ? "신규 진입 자제" : "—"}
        </p>
      </div>

      {/* 핵심 지표 3개 */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "체제 점수", value: regime.weighted_score != null ? regime.weighted_score.toFixed(2) : "—", sub: regime.regime_label ?? regime.regime ?? "—", color: "#ffb020" },
          { label: "스크리닝", value: String(picks.length), sub: isKR ? "KOSPI 종목" : "S&P 종목", color: "#ece7d8" },
          { label: "마켓 게이트", value: gate.gate ?? "—", sub: isKR ? (gate.reason ?? "") : `avg ${gate.avg_score?.toFixed(1) ?? "—"}`, color: VERDICT_COLOR[gate.gate] ?? "#ece7d8" },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="rounded-xl p-3 flex flex-col gap-1" style={{ background: "var(--bg-card)" }}>
            <p className="text-[11px] uppercase tracking-wide" style={{ color: "#726b58" }}>{label}</p>
            <p className="text-2xl font-black leading-none" style={{ color }}>{value}</p>
            <p className="text-[11px] truncate" style={{ color: "#726b58" }}>{sub}</p>
          </div>
        ))}
      </div>

      {/* SPY / KOSPI 예측 */}
      {spy && (
        <div className="rounded-xl p-3 flex items-center justify-between" style={{ background: "var(--bg-card)" }}>
          <div>
            <p className="text-[12px] uppercase tracking-wide mb-1" style={{ color: "#726b58" }}>{predTitle}</p>
            <p className="text-xl font-black" style={{ color: dirInfo(spy.direction).color }}>
              {dirInfo(spy.direction).text}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[12px]" style={{ color: "#726b58" }}>확률</p>
            <p className="text-xl font-bold text-white">
              {spy.probability != null ? `${Math.round(spy.probability * 100)}%` : "—"}
            </p>
          </div>
        </div>
      )}

      {/* 상위 픽 */}
      {top5.length > 0 && (
        <div className="rounded-xl p-3" style={{ background: "var(--bg-card)" }}>
          <p className="text-[12px] uppercase tracking-wide mb-2" style={{ color: "#726b58" }}>
            상위 {isKR ? "KOSPI" : "알파"} 픽
          </p>
          <div className="space-y-2">
            {top5.map((p: any) => (
              <div key={p.symbol} className="flex items-center gap-2">
                <span className="w-5 h-5 rounded text-[11px] font-black flex items-center justify-center shrink-0"
                  style={{ background: "#ffb02022", color: "#ffb020", border: "1px solid #ffb02044" }}>
                  {p.grade}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-base font-bold text-white truncate block">{p.name ?? p.symbol}</span>
                  {p.name && <span className="text-[11px] font-mono" style={{ color: "#726b58" }}>{p.symbol}</span>}
                </div>
                <span className="text-base font-bold shrink-0" style={{ color: "#ffb020" }}>{p.composite_score?.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {picks.length === 0 && Object.keys(sensors).length === 0 && (
        <div className="rounded-xl p-4 text-center text-base" style={{ background: "var(--bg-card)", color: "#726b58" }}>
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
        <span className="text-[13px] font-bold px-2 py-0.5 rounded" style={{ background: "#262112", color: "#726b58" }}>
          <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
        </span>
        <h1 className="text-2xl font-bold text-white">
          {isKR ? "한국 주식 마켓 인텔리전스" : "미국 주식 마켓 인텔리전스"}
        </h1>
        <span className="rounded px-2 py-0.5 text-[13px] font-bold" style={{ background: "#ffb02022", color: "#ffb020", border: "1px solid #ffb02044" }}>
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
          color="#ffb020"
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
          color={VERDICT_COLOR[gate.gate] ?? "#ece7d8"}
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
                <h2 className="stat-label" style={{ fontSize: 13 }}>핵심 체제 지표</h2>
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
                          <p className="text-[13px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>
                            {sensorLabel[key] ?? key}
                          </p>
                          <p className="text-base font-bold" style={{ color: info.color }}>{info.text}</p>
                          <p className="text-[13px] font-mono mt-0.5" style={{ color: "var(--text-faint)" }}>{val.toFixed(2)}</p>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          )}

          {/* 지수 주요 지표 (US/KR 공통) */}
          {(() => {
            const idxLast = isKR ? regime.kospi_last : regime.spy_last;
            const idxSma  = isKR ? regime.kospi_sma200 : regime.spy_sma200;
            if (!idxLast) return null;
            return (
              <div className="bg-card rounded-lg p-3">
                <h2 className="stat-label mb-2" style={{ fontSize: 13 }}>{indexName} 주요 지표</h2>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: isKR ? "KOSPI" : "S&P 500", val: idxLast?.toLocaleString(), color: "var(--text-primary)" },
                    { label: "SMA 200", val: idxSma?.toLocaleString(), color: idxLast >= (idxSma ?? 0) ? "#4ade80" : "#f87171" },
                    { label: "변동성(60일)", val: regime.vol_60d != null ? `${regime.vol_60d.toFixed(1)}%` : "—", color: regime.vol_60d > 25 ? "#f87171" : "#facc15" },
                    { label: "모멘텀(20일)", val: regime.mom_20d != null ? `${regime.mom_20d >= 0 ? "+" : ""}${regime.mom_20d.toFixed(1)}%` : "—", color: regime.mom_20d != null ? (regime.mom_20d >= 0 ? "#4ade80" : "#f87171") : "var(--text-muted)" },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="rounded-lg p-3 text-center" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
                      <p className="text-[13px] mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
                      <p className="text-lg font-bold" style={{ color }}>{val ?? "—"}</p>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Top picks */}
          {top5.length > 0 && (
            <div className="bg-card rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <h2 className="stat-label" style={{ fontSize: 13 }}>상위 5 {isKR ? "KOSPI" : "알파"} 픽</h2>
                  <InfoTooltip content="복합 점수 상위 5개 종목입니다." />
                </div>
              </div>
              <div className="space-y-2">
                {top5.map((p: any) => (
                  <div key={p.symbol} className="flex items-center gap-3 py-2 border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                    <span className="w-6 h-6 rounded flex items-center justify-center text-[13px] font-black" style={{ background: "#ffb02022", color: "#ffb020", border: "1px solid #ffb02044" }}>
                      {p.grade}
                    </span>
                    <div className="flex-1 min-w-0">
                      {p.name
                        ? <><span className="text-base font-bold text-white">{p.name}</span>
                            <span className="ml-2 text-[13px] font-mono" style={{ color: "var(--text-muted)" }}>{p.symbol}</span></>
                        : <span className="text-base font-bold text-white">{p.symbol}</span>
                      }
                      {p.sector && <span className="ml-2 text-[13px]" style={{ color: "var(--text-faint)" }}>{p.sector}</span>}
                    </div>
                    <span className="text-base font-bold" style={{ color: "#ffb020" }}>{p.composite_score?.toFixed(1)}</span>
                    <span className="text-[13px] px-2 py-0.5 rounded" style={{ background: "#111009", color: "var(--text-secondary)" }}>{p.action}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!data || (picks.length === 0 && Object.keys(sensors).length === 0) && (
            <div className="bg-card rounded-lg p-3 text-center text-base text-[#726b58]">
              데이터 없음. GitHub → Actions → Daily Analysis 실행 후 재확인하세요.
            </div>
          )}
        </div>

        {/* Right */}
        <div className="space-y-3">
          {/* Verdict card */}
          <div
            className="rounded-lg p-5 flex flex-col items-center justify-center gap-2 text-center"
            style={{
              background: verdict === "GO" ? "#4ade8018" : verdict === "CAUTION" ? "#facc1518" : "#f8717118",
              border: `1px solid ${verdictColor}44`,
            }}
          >
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-bold uppercase tracking-widest" style={{ color: verdictColor }}>종합 판단</span>
            </div>
            <p className="text-5xl font-black" style={{ color: verdictColor }}>{verdict}</p>
            <p className="text-[13px] text-[#726b58]">
              체제: <span className="text-white font-semibold">{regime.regime?.replace("_", " ") ?? "—"}</span>
              &nbsp;·&nbsp;점수: <span className="text-white font-semibold">{regime.weighted_score?.toFixed(2) ?? "—"}</span>
            </p>
            {isKR && gate.reason && (
              <p className="text-[13px] text-[#a39c88] text-center px-2">{gate.reason}</p>
            )}
          </div>

          {/* SPY / KOSPI 다음 주 방향 예측 */}
          {spy && (
            <div className="bg-card rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <h2 className="stat-label" style={{ fontSize: 13 }}>{predTitle}</h2>
                <InfoTooltip content={
                  spy.model_type === "rule_based"
                    ? "체제 지표 기반의 다음 주 방향 추정입니다. (ML 예측 데이터가 쌓이면 자동 전환)"
                    : `LightGBM 모델의 다음 주 ${isKR ? "KOSPI" : "SPY"} 방향 예측입니다.`
                } />
              </div>
              <p className="text-3xl font-black mb-1" style={{ color: dirInfo(spy.direction).color }}>
                {dirInfo(spy.direction).text}
              </p>
              <p className="text-base font-semibold text-white">
                확률 {spy.probability != null ? `${Math.round(spy.probability * 100)}%` : "—"}
              </p>
              {spy.cv_accuracy != null && (
                <p className="text-[13px] mt-1" style={{ color: "var(--text-muted)" }}>
                  모델 정확도 {Math.round(spy.cv_accuracy * 100)}%
                </p>
              )}
              {spy.model_type === "rule_based" && (
                <p className="text-[13px] mt-1" style={{ color: "var(--text-faint)" }}>
                  체제 지표 기반 추정
                </p>
              )}
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
