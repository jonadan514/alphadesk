"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";

const US_SENSOR_META: Record<string, { label: string; weight: string; desc: string }> = {
  vix:         { label: "VIX",         weight: "30%", desc: "시장 공포지수. 낮을수록 투자심리 안정 → risk_on 신호" },
  trend:       { label: "TREND",       weight: "25%", desc: "S&P 500이 SMA200 위에 있는지. 장기 추세 방향 측정" },
  breadth:     { label: "BREADTH",     weight: "18%", desc: "상승 종목 비율. 시장 전반의 참여도 · 건강성" },
  credit:      { label: "CREDIT",      weight: "15%", desc: "하이일드 스프레드. 높을수록 신용 리스크 경고" },
  yield_curve: { label: "YIELD CURVE", weight: "12%", desc: "장단기 금리차. 역전 시 경기침체 선행 신호" },
  put_call:    { label: "PUT/CALL",    weight: "—",   desc: "옵션 헤징 강도. 높을수록 시장 하방 베팅 증가" },
};

// 가중치는 src/analyzers/kr_market_regime.py WEIGHTS와 일치해야 함
const KR_SENSOR_META: Record<string, { label: string; weight: string; desc: string }> = {
  trend:      { label: "TREND",      weight: "30%", desc: "KOSPI가 SMA200 위에 있는지. 장기 추세 방향" },
  volatility: { label: "VOLATILITY", weight: "20%", desc: "60일 변동성. 높을수록 시장 불안정 · 리스크 확대" },
  momentum:   { label: "MOMENTUM",   weight: "20%", desc: "60일 수익률. 중기 방향성과 모멘텀 강도" },
  breadth:    { label: "BREADTH",    weight: "15%", desc: "상승 종목 비율. KOSPI 전반의 흐름과 건강성" },
  usdkrw:     { label: "USD/KRW",    weight: "15%", desc: "원/달러 환율 추세. 원화 약세 = 외국인 자금 이탈 위험" },
};

type RegimeKey = "risk_on" | "neutral" | "risk_off" | "crisis";

const REGIME_GUIDE: Record<RegimeKey, { icon: string; color: string; text: string }[]> = {
  risk_on: [
    { icon: "✓", color: "#39ff8f", text: "신규 진입 가능" },
    { icon: "✓", color: "#39ff8f", text: "포지션 비중 확대" },
    { icon: "✓", color: "#39ff8f", text: "BUY 등급 종목 우선 편입" },
    { icon: "✓", color: "#39ff8f", text: "손절선 -10% 적용" },
  ],
  neutral: [
    { icon: "~", color: "#facc15", text: "기존 포지션 유지" },
    { icon: "~", color: "#facc15", text: "신규 진입은 선별적으로" },
    { icon: "~", color: "#facc15", text: "추세 재확인 후 결정" },
    { icon: "~", color: "#facc15", text: "손절선 -8% 준수" },
  ],
  risk_off: [
    { icon: "✗", color: "#f97316", text: "신규 진입 자제" },
    { icon: "✗", color: "#f97316", text: "보유 비중 단계적 축소" },
    { icon: "✗", color: "#f97316", text: "방어주 · 현금 비중 확대" },
    { icon: "✗", color: "#f97316", text: "손절선 -5% 엄수" },
  ],
  crisis: [
    { icon: "✗", color: "#ef4444", text: "신규 진입 금지" },
    { icon: "✗", color: "#ef4444", text: "포지션 최소화" },
    { icon: "✗", color: "#ef4444", text: "현금 비중 최대화" },
    { icon: "✗", color: "#ef4444", text: "손절선 -3% 즉시 실행" },
  ],
};

function sensorInfo(score: number) {
  if (score >= 1.5) return { text: "강세", color: "#39ff8f" };
  if (score >= 0.5) return { text: "중립", color: "#facc15" };
  if (score >= 0)   return { text: "약세", color: "#f97316" };
  return { text: "위기", color: "#ef4444" };
}

const STOP_LOSS: Record<string, { pct: string; mdd: string; strategy: string; desc: string }> = {
  risk_on:  { pct: "-10%", mdd: "-15%", strategy: "공격적",     desc: "시장 강세 — 포지션 확대 가능" },
  neutral:  { pct: "-8%",  mdd: "-12%", strategy: "표준",       desc: "관망 — 기존 포지션 유지" },
  risk_off: { pct: "-5%",  mdd: "-8%",  strategy: "방어적",     desc: "약세 신호 — 비중 축소 권장" },
  crisis:   { pct: "-3%",  mdd: "-5%",  strategy: "현금 최대화", desc: "위기 국면 — 현금 전환 권장" },
};

const REGIME_BG: Record<string, string> = {
  risk_on:  "rgba(57,255,143,0.06)",
  neutral:  "rgba(250,204,21,0.06)",
  risk_off: "rgba(249,115,22,0.06)",
  crisis:   "rgba(239,68,68,0.06)",
};

const REGIME_LABEL_KO: Record<string, string> = {
  risk_on:  "Risk On (강세)",
  neutral:  "Neutral (중립)",
  risk_off: "Risk Off (약세)",
  crisis:   "Crisis (위기)",
};

export default function RegimePage() {
  const { market } = useMarket();
  const [data, setData] = useState<any>(null);

  const [usMacro, setUsMacro] = useState<any>(null);

  useEffect(() => {
    setData(null);
    setUsMacro(null);
    const url = market === "KR" ? "/api/data/kr/regime" : "/api/data/regime";
    fetch(url).then((r) => r.json()).then(setData);
    // KR: 한국 증시에 영향 주는 글로벌(미국) 매크로도 함께 로드
    if (market === "KR") {
      fetch("/api/data/regime")
        .then((r) => r.json())
        .then((d) => setUsMacro(d?.macro_snapshot ?? null))
        .catch(() => {});
    }
  }, [market]);

  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="bg-card rounded-lg p-3 text-center text-sm" style={{ color: "var(--text-muted)" }}>
        {data === null ? "로딩 중…" : `${market === "KR" ? "한국" : "미국"} 시장 데이터가 없습니다.`}
      </div>
    );
  }

  const sensorMeta = market === "KR" ? KR_SENSOR_META : US_SENSOR_META;
  const sensors: Record<string, number> = data.sensor_scores ?? {};
  const regime = (data.regime ?? "neutral") as RegimeKey;
  const sl = STOP_LOSS[regime] ?? { pct: "—", mdd: "—", strategy: "—", desc: "" };
  const guide = REGIME_GUIDE[regime] ?? [];

  const regimeLabel = data.regime_label ?? REGIME_LABEL_KO[regime] ?? regime;
  const indexName   = market === "KR" ? "KOSPI" : "S&P 500";
  const indexLast   = market === "KR" ? data.kospi_last : data.spy_last;
  const indexSma200 = market === "KR" ? data.kospi_sma200 : data.spy_sma200;

  const regimeColor = regime === "risk_on" ? "#39ff8f"
    : regime === "neutral" ? "#facc15"
    : regime === "risk_off" ? "#f97316"
    : "#ef4444";

  const sensorEntries = Object.entries(sensors);

  return (
    <div className="space-y-2">
      {/* ── 상단: 체제 히어로 + 리스크 파라미터 ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">

        {/* 체제 상태 (2열) */}
        <div
          className="md:col-span-2 rounded-xl p-3 flex flex-col gap-2"
          style={{ background: REGIME_BG[regime] ?? "var(--bg-card)", border: `1px solid ${regimeColor}33` }}
        >
          {/* 상단: 이름 + 점수 */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[12px] font-semibold tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>
                {market === "KR" ? "KOSPI" : "S&P 500"} 시장 체제
              </p>
              <h1 className="text-[28px] font-black leading-none tracking-tight" style={{ color: regimeColor }}>
                {regimeLabel}
              </h1>
              <p className="text-[13px] mt-1 font-medium" style={{ color: "var(--text-secondary)" }}>{sl.desc}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-[12px] mb-0.5" style={{ color: "var(--text-muted)" }}>체제 점수</p>
              <p className="text-[28px] font-black font-mono" style={{ color: regimeColor }}>
                {data.weighted_score?.toFixed(2) ?? "—"}
              </p>
              <p className="text-[11px] mt-1" style={{ color: "var(--text-faint)" }}>{data.computed_at ?? data.collected_at ?? ""}</p>
            </div>
          </div>

          {/* 중단: 행동 가이드 */}
          {guide.length > 0 && (
            <div className="grid grid-cols-2 gap-1.5">
              {guide.map((g, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-lg px-3 py-2"
                  style={{ background: `${g.color}0d`, border: `1px solid ${g.color}28` }}
                >
                  <span className="text-[14px] font-black shrink-0" style={{ color: g.color }}>{g.icon}</span>
                  <span className="text-[13px] font-semibold" style={{ color: "var(--text-primary)" }}>{g.text}</span>
                </div>
              ))}
            </div>
          )}

          {/* 하단: 핵심 지표 행 */}
          <div className="flex items-center gap-5 pt-2" style={{ borderTop: `1px solid ${regimeColor}22` }}>
            {indexLast && (
              <div>
                <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>{indexName}</p>
                <p className="text-[15px] font-bold text-white">{indexLast.toLocaleString()}</p>
              </div>
            )}
            {indexSma200 && (
              <div>
                <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>SMA 200</p>
                <p className="text-[15px] font-bold" style={{ color: "var(--text-secondary)" }}>{indexSma200.toLocaleString()}</p>
              </div>
            )}
            {data.vol_60d != null && (
              <div>
                <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>변동성 60일</p>
                <p className="text-[15px] font-bold" style={{ color: data.vol_60d > 30 ? "#ef4444" : data.vol_60d > 20 ? "#f97316" : "#facc15" }}>
                  {data.vol_60d.toFixed(1)}%
                </p>
              </div>
            )}
            {data.mom_20d != null && (
              <div>
                <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>모멘텀 20일</p>
                <p className="text-[15px] font-bold" style={{ color: data.mom_20d >= 0 ? "#39ff8f" : "#ef4444" }}>
                  {data.mom_20d >= 0 ? "+" : ""}{data.mom_20d.toFixed(2)}%
                </p>
              </div>
            )}
            {data.usdkrw_last != null && (
              <div>
                <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>USD/KRW</p>
                <p className="text-[15px] font-bold" style={{ color: (data.usdkrw_chg_20d ?? 0) > 0 ? "#ef4444" : "#39ff8f" }}>
                  {data.usdkrw_last.toLocaleString()}
                  {data.usdkrw_chg_20d != null && (
                    <span className="text-[12px] ml-1">
                      ({data.usdkrw_chg_20d >= 0 ? "+" : ""}{data.usdkrw_chg_20d.toFixed(1)}%)
                    </span>
                  )}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* 리스크 파라미터 (1열) */}
        <div className="bg-card rounded-xl p-3 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <h2 className="stat-label">리스크 파라미터</h2>
            <InfoTooltip content="현재 체제에서 권장되는 리스크 관리 기준입니다." />
          </div>
          <div className="flex flex-col gap-1.5 flex-1">
            <div className="flex-1 rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid #ef444433" }}>
              <p className="text-[12px] mb-0.5" style={{ color: "var(--text-muted)" }}>종목별 손절선</p>
              <p className="text-[22px] font-black text-[#ef4444] leading-none">{sl.pct}</p>
              <p className="text-[11px] mt-1" style={{ color: "var(--text-faint)" }}>매수가 대비 이 수준 도달 시 즉시 매도</p>
            </div>
            <div className="flex-1 rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid #f9731633" }}>
              <p className="text-[12px] mb-0.5" style={{ color: "var(--text-muted)" }}>포트폴리오 MDD 경고</p>
              <p className="text-[22px] font-black text-[#f97316] leading-none">{sl.mdd}</p>
              <p className="text-[11px] mt-1" style={{ color: "var(--text-faint)" }}>전체 자산 최대 낙폭 경보 기준</p>
            </div>
            <div className="flex-1 rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <p className="text-[12px] mb-0.5" style={{ color: "var(--text-muted)" }}>운용 전략</p>
              <p className="text-[18px] font-black text-white leading-snug">{sl.strategy}</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── 센서 상태 ── */}
      {sensorEntries.length > 0 && (
        <div className="bg-card rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <h2 className="stat-label">센서 상태</h2>
            <InfoTooltip content="각 센서의 점수를 가중 합산하여 시장 체제를 판별합니다." />
          </div>
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: `repeat(3, minmax(0, 1fr))` }}
          >
            {sensorEntries.map(([key, val]) => {
              const meta = sensorMeta[key] ?? { label: key.toUpperCase(), weight: "—", desc: "" };
              const info = sensorInfo(val);
              const barPct = Math.min(Math.max(((val + 1) / 3) * 100, 0), 100);
              return (
                <div key={key} className="rounded-lg p-2.5 flex flex-col gap-1" style={{ background: "var(--bg-inset)", border: `1px solid ${info.color}33` }}>
                  {/* 헤더: 라벨 + 가중치 */}
                  <div className="flex items-center justify-between">
                    <p className="text-[12px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                      {meta.label}
                    </p>
                    <span
                      className="text-[11px] font-mono px-1.5 py-0.5 rounded"
                      style={{ background: `${info.color}18`, color: info.color }}
                    >
                      {meta.weight}
                    </span>
                  </div>
                  {/* 상태 + 점수 */}
                  <div className="flex items-end justify-between">
                    <p className="text-[16px] font-black" style={{ color: info.color }}>{info.text}</p>
                    <p className="text-[12px] font-mono font-bold" style={{ color: "var(--text-faint)" }}>{val.toFixed(2)}</p>
                  </div>
                  {/* 게이지 바 */}
                  <div className="h-1 rounded-full" style={{ background: "var(--bg-raised)" }}>
                    <div className="h-full rounded-full" style={{ width: `${barPct}%`, background: info.color }} />
                  </div>
                  {/* 설명 */}
                  {meta.desc && (
                    <p className="text-[12px] leading-snug" style={{ color: "var(--text-faint)" }}>
                      {meta.desc}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 매크로 스냅샷 — US: 자체 데이터 / KR: 글로벌(미국) 매크로 + 환율 */}
      {(() => {
        const macro: Record<string, unknown> | null =
          market === "US" ? (data.macro_snapshot ?? null) : usMacro;
        if (!macro) return null;

        const META: Record<string, { label: string; desc: string }> = {
          vix_current: { label: "VIX 현재",    desc: "공포지수. 15↓ 안정, 30↑ 경계" },
          vix_ma20:    { label: "VIX 20일 평균", desc: "현재 VIX 대비 높으면 변동성 확대 중" },
          hy_spread:   { label: "하이일드 스프레드", desc: "신용위험. 5%↑ 시 위험 자산 경계" },
          t10y2y:      { label: "장단기 금리차", desc: "음수(역전) 지속 시 경기침체 선행 신호" },
          dff:         { label: "기준금리 (Fed)", desc: "연준 기준금리. 높을수록 긴축 환경" },
        };

        const entries: { key: string; label: string; desc: string; val: string }[] =
          Object.entries(macro).map(([k, v]) => {
            const meta = META[k] ?? { label: k.replace(/_/g, " ").toUpperCase(), desc: "" };
            return { key: k, ...meta, val: v != null ? String(v) : "—" };
          });

        // KR: 원/달러 환율을 첫 칸에 추가 (외국인 수급 프록시)
        if (market === "KR" && data.usdkrw_last != null) {
          entries.unshift({
            key: "usdkrw",
            label: "USD/KRW",
            desc: "원화 약세(상승) = 외국인 자금 이탈 위험",
            val: `${data.usdkrw_last.toLocaleString()}${data.usdkrw_chg_20d != null ? ` (${data.usdkrw_chg_20d >= 0 ? "+" : ""}${data.usdkrw_chg_20d.toFixed(1)}%)` : ""}`,
          });
        }

        return (
          <div className="bg-card rounded-xl p-3">
            <div className="flex items-center gap-2 mb-2">
              <h2 className="stat-label">{market === "KR" ? "글로벌 매크로 스냅샷" : "매크로 스냅샷"}</h2>
              {market === "KR" && (
                <InfoTooltip content="한국 증시는 미국 매크로(VIX·금리)와 환율에 민감하게 반응합니다. 미국 시장 분석에서 수집한 지표입니다." />
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              {entries.map(({ key, label, desc, val }) => (
                <div key={key} className="rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
                  <p className="text-[12px] font-semibold" style={{ color: "var(--text-muted)" }}>{label}</p>
                  <p className="text-[18px] font-black text-white leading-none mt-1">{val}</p>
                  {desc && (
                    <p className="text-[11px] mt-1.5 leading-snug" style={{ color: "var(--text-faint)" }}>{desc}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
