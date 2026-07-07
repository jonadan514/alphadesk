"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";
import { stopLossPct } from "@/src/lib/stopLoss";

/* ── 유틸 ─────────────────────────────────────────── */
function pct(v: number, digits = 1) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;
}
function usd(v: number) {
  return `$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
function krw(v: number) {
  return `₩${Math.round(Math.abs(v)).toLocaleString()}`;
}

const REGIME_LABEL: Record<string, string> = {
  risk_on: "강세", neutral: "중립", risk_off: "약세", crisis: "위기",
};
const REGIME_COLOR: Record<string, string> = {
  risk_on: "#39ff8f", neutral: "#facc15", risk_off: "#f97316", crisis: "#ef4444",
};

/* ── 포지션 계산기 ──────────────────────────────────── */
function PositionCalculator({ currency = "USD" }: { currency?: "USD" | "KRW" }) {
  const [portfolio, setPortfolio] = useState(currency === "KRW" ? 50000000 : 100000);
  const [riskPct,   setRiskPct]   = useState(1);
  const [stopLoss,  setStopLoss]  = useState(5);
  const [price,     setPrice]     = useState(currency === "KRW" ? 50000 : 150);
  const [winRate,   setWinRate]   = useState(55);
  const [rr,        setRr]        = useState(2);

  const riskAmount  = portfolio * (riskPct / 100);
  const maxPosition = riskAmount / (stopLoss / 100);
  const maxShares   = Math.floor(maxPosition / price);
  const positionPct = (maxPosition / portfolio) * 100;
  const kellyF      = Math.max(0, winRate / 100 - (1 - winRate / 100) / rr);
  const kellyPct    = Math.min(kellyF * 100, 25);
  const kellyAmount = portfolio * (kellyPct / 100);
  const kellyShares = Math.floor(kellyAmount / price);
  const fmt = (n: number) => currency === "KRW" ? `₩${Math.round(n).toLocaleString()}` : `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

  const inputCls = "w-full rounded-lg px-3 py-2 text-sm font-mono text-white outline-none";
  const inputStyle = { background: "var(--bg-inset)", border: "1px solid var(--border)" };

  return (
    <div className="bg-card rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="stat-label">포지션 계산기</h2>
        <InfoTooltip content="총 자산에서 허용 손실 비중과 손절선을 입력하면 적정 매수 수량을 알려줍니다." />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 grid grid-cols-2 gap-3">
          {[
            { label: `총 자산 ${currency === "KRW" ? "(₩)" : "($)"}`, val: portfolio, set: setPortfolio, step: undefined },
            { label: `종목 주가 ${currency === "KRW" ? "(₩)" : "($)"}`, val: price, set: setPrice, step: undefined },
            { label: "허용 손실 (%)", val: riskPct, set: setRiskPct, step: 0.1 },
            { label: "손절선 (%)", val: stopLoss, set: setStopLoss, step: 0.5 },
            { label: "예상 승률 (%)·켈리", val: winRate, set: setWinRate, step: 1 },
            { label: "손익비 R:R·켈리", val: rr, set: setRr, step: 0.1 },
          ].map(({ label, val, set, step }) => (
            <label key={label} className="block">
              <span className="text-[12px] block mb-1" style={{ color: "var(--text-muted)" }}>{label}</span>
              <input type="number" value={val} step={step}
                onChange={e => set(Number(e.target.value))}
                className={inputCls} style={inputStyle}
                onWheel={e => e.currentTarget.blur()} />
            </label>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex-1 rounded-lg p-3 text-center" style={{ background: "var(--bg-inset)", border: "1px solid #39ff8f33" }}>
            <p className="text-[12px] mb-1" style={{ color: "var(--text-muted)" }}>고정 비율 매수 수량</p>
            <p className="text-2xl font-black" style={{ color: "#39ff8f" }}>{maxShares.toLocaleString()}<span className="text-sm font-normal ml-1">주</span></p>
            <p className="text-[12px] mt-1" style={{ color: "var(--text-muted)" }}>{fmt(maxPosition)} ({positionPct.toFixed(1)}%)</p>
            <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>최대 손실 {fmt(riskAmount)}</p>
          </div>
          <div className="flex-1 rounded-lg p-3 text-center" style={{ background: "var(--bg-inset)", border: "1px solid #facc1533" }}>
            <p className="text-[12px] mb-1" style={{ color: "var(--text-muted)" }}>켈리 기준 매수 수량</p>
            <p className="text-2xl font-black" style={{ color: "#facc15" }}>{kellyShares.toLocaleString()}<span className="text-sm font-normal ml-1">주</span></p>
            <p className="text-[12px] mt-1" style={{ color: "var(--text-muted)" }}>{fmt(kellyAmount)} ({kellyPct.toFixed(1)}%)</p>
            <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>f={kellyF.toFixed(3)}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── KR 리스크 뷰 ─────────────────────────────────── */
function KRRiskView() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    fetch("/api/data/kr/risk").then(r => r.json()).then(setData);
  }, []);

  if (!data) return <div className="bg-card rounded-xl p-4 text-sm" style={{ color: "var(--text-muted)" }}>로딩 중…</div>;

  const regime = data.regime ?? "neutral";
  const regColor = REGIME_COLOR[regime] ?? "#facc15";
  const rlColor = data.risk_level === "DANGER" ? "#ef4444" : data.risk_level === "WATCH" ? "#facc15" : "#39ff8f";
  const rlKo = data.risk_level === "DANGER" ? "위험" : data.risk_level === "WATCH" ? "주의" : "정상";
  const sensors: Record<string, number> = data.sensor_scores ?? {};

  const volColor = data.vol_60d > 35 ? "#ef4444" : data.vol_60d > 25 ? "#f97316" : "#39ff8f";
  const volText  = data.vol_60d > 35 ? "고변동 — 비중 축소 권장" : data.vol_60d > 25 ? "경계 — 분할 매수 권장" : "안정 구간";

  return (
    <div className="space-y-3">
      {/* 히어로 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="md:col-span-2 rounded-xl p-4" style={{ background: `${rlColor}0d`, border: `1px solid ${rlColor}33` }}>
          <p className="text-[12px] font-semibold uppercase tracking-widest mb-1" style={{ color: "var(--text-muted)" }}><FlagIcon market="KR" size={13} />{" "}KOSPI 리스크 모니터</p>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-4xl font-black" style={{ color: rlColor }}>{rlKo}</span>
            <span className="text-[13px] px-2 py-0.5 rounded font-bold" style={{ background: `${regColor}18`, color: regColor, border: `1px solid ${regColor}33` }}>
              시장 {REGIME_LABEL[regime] ?? regime}
            </span>
          </div>
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
            {data.risk_level === "DANGER" ? "즉각적인 리스크 관리가 필요합니다. 손절 기준을 재확인하세요." :
             data.risk_level === "WATCH" ? "일부 지표가 경계 구간입니다. 신규 진입 시 신중하게 접근하세요." :
             "포트폴리오가 안정적인 상태입니다. 현재 전략을 유지하세요."}
          </p>
          <p className="text-[12px] mt-2" style={{ color: "var(--text-faint)" }}>{data.computed_at} · KOSPI {data.kospi_last?.toLocaleString()}</p>
        </div>
        <div className="bg-card rounded-xl p-4 flex flex-col gap-2">
          {[
            { label: "KOSPI", val: data.kospi_last?.toLocaleString(), sub: `SMA200 : ${data.kospi_sma200?.toLocaleString()}`, color: "var(--text-primary)" },
            { label: "변동성 (60일)", val: `${data.vol_60d?.toFixed(1)}%`, sub: volText, color: volColor },
            { label: "20일 모멘텀", val: `${data.mom_20d >= 0 ? "+" : ""}${data.mom_20d?.toFixed(2)}%`, sub: data.mom_20d > 3 ? "상승 추세" : data.mom_20d > 0 ? "약한 상승" : data.mom_20d > -3 ? "약한 하락" : "하락 추세", color: data.mom_20d >= 0 ? "#39ff8f" : "#ef4444" },
          ].map(({ label, val, sub, color }) => (
            <div key={label} className="rounded-lg px-3 py-2" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>{label}</p>
              <p className="text-base font-black" style={{ color }}>{val}</p>
              <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>{sub}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 리스크 센서 */}
      {Object.keys(sensors).length > 0 && (
        <div className="bg-card rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <h2 className="stat-label">리스크 센서</h2>
            <InfoTooltip content="각 지표가 시장 안정성에 어떤 신호를 보내는지 나타냅니다." />
          </div>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(sensors).map(([key, val]) => {
              const color = val >= 1 ? "#39ff8f" : val >= 0 ? "#facc15" : "#ef4444";
              const statusKo = val >= 1 ? "안정" : val >= 0 ? "주의" : "위험";
              const barPct = Math.min(Math.max(((val + 1) / 3) * 100, 0), 100);
              return (
                <div key={key} className="rounded-lg p-3" style={{ background: "var(--bg-inset)", border: `1px solid ${color}33` }}>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[12px] font-bold uppercase" style={{ color: "var(--text-muted)" }}>{key}</p>
                    <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: `${color}18`, color }}>{statusKo}</span>
                  </div>
                  <div className="h-1 rounded-full mb-1" style={{ background: "var(--bg-raised)" }}>
                    <div className="h-full rounded-full" style={{ width: `${barPct}%`, background: color }} />
                  </div>
                  <p className="text-[12px] font-mono" style={{ color: "var(--text-faint)" }}>{val.toFixed(2)}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 리스크 관리 가이드 */}
      <div className="bg-card rounded-xl p-4">
        <h2 className="stat-label mb-3">지금 적용할 기준</h2>
        <div className="grid grid-cols-2 gap-2">
          {[
            { label: "손절선", val: `-${stopLossPct(regime)}%`, desc: "이 수준 도달 시 즉시 매도" },
            { label: "포트폴리오 MDD 경고", val: data.vol_60d > 25 ? "-15%" : "-12%", desc: "전체 자산 최대 낙폭 경보" },
            { label: "권장 투자 비중", val: regime === "risk_on" ? "70~80%" : regime === "neutral" ? "50~60%" : regime === "risk_off" ? "30~40%" : "10~20%", desc: "현재 체제 기준 권장 비중" },
            { label: "고변동성 대응", val: data.vol_60d > 35 ? "비중 축소" : data.vol_60d > 25 ? "분할 매수" : "정상 유지", desc: `현재 변동성 ${data.vol_60d?.toFixed(1)}% 기준` },
          ].map(({ label, val, desc }) => (
            <div key={label} className="rounded-lg p-3" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>{label}</p>
              <p className="text-base font-black text-white mt-0.5">{val}</p>
              <p className="text-[12px] mt-0.5" style={{ color: "var(--text-faint)" }}>{desc}</p>
            </div>
          ))}
        </div>
      </div>

      <PositionCalculator currency="KRW" />
    </div>
  );
}

/* ── US 리스크 뷰 (메인) ───────────────────────────── */
export default function RiskPage() {
  const { market } = useMarket();
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setDetail(null);
    setLoading(true);
    fetch("/api/data/risk-detail")
      .then(r => r.json())
      .then(d => { setDetail(d); setLoading(false); });
  }, []);

  if (market === "KR") return <KRRiskView />;
  if (loading) return <div className="text-sm" style={{ color: "var(--text-muted)" }}>로딩 중…</div>;

  if (!detail) return (
    <div className="space-y-3">
      <div className="bg-card rounded-xl p-4">
        <p className="font-semibold text-white mb-1">데이터가 없습니다</p>
        <p className="text-[12px] mb-2" style={{ color: "var(--text-muted)" }}>alpharun 실행 후 자동으로 계산됩니다.</p>
        <code className="block text-[12px] rounded-lg px-3 py-2" style={{ background: "var(--bg-inset)", color: "#39ff8f" }}>alpharun</code>
      </div>
    </div>
  );

  const regime     = detail.regime ?? "neutral";
  const status     = detail.risk_status ?? "WATCH";
  const alerts: any[]   = detail.alerts ?? [];
  const positions: any[] = detail.position_sizing ?? [];
  const sectors: any[]   = detail.sector_concentration ?? [];
  const corrPairs: any[] = detail.high_corr_pairs ?? [];
  const compVar: any[]   = detail.component_var ?? [];
  const cdarTable: any[] = detail.cdar_cvar ?? [];

  const statusColor = status === "NORMAL" ? "#39ff8f" : status === "WATCH" ? "#facc15" : "#ef4444";
  const statusKo    = status === "NORMAL" ? "정상" : status === "WATCH" ? "주의" : "위험";
  const statusDesc  = status === "NORMAL"
    ? "모든 지표가 안정 범위입니다. 현재 전략을 유지하세요."
    : status === "WATCH"
    ? "일부 지표가 경계 구간입니다. 신규 진입 시 신중하게 접근하세요."
    : "즉각적인 리스크 관리가 필요합니다. 손절 기준을 재확인하세요.";

  const regColor = REGIME_COLOR[regime] ?? "#facc15";
  const investedPct = Math.round((detail.invested_pct ?? 0) * 100);
  const cashPct     = 100 - investedPct;
  const recPct      = Math.round((detail.recommended_alloc ?? 0.6) * 100);
  const varPct      = detail.portfolio_var ? Math.abs(detail.portfolio_var * 100) : 0;
  const varWarning  = varPct > 1.5;

  const maxSector  = Math.max(...sectors.map((s: any) => s.weight_pct), 0.01);
  const maxCompVar = Math.max(...compVar.map((c: any) => Math.abs(c.cvar_pct)), 0.001);
  const maxPosVal  = Math.max(...positions.map((p: any) => p.value), 1);

  return (
    <div className="space-y-3">

      {/* ── 1. 포트폴리오 건강도 히어로 ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* 종합 상태 */}
        <div className="md:col-span-2 rounded-xl p-4" style={{ background: `${statusColor}0d`, border: `1px solid ${statusColor}33` }}>
          <p className="text-[12px] font-semibold uppercase tracking-widest mb-2" style={{ color: "var(--text-muted)" }}>
            <FlagIcon market="US" size={13} />{" "}S&P 500 포트폴리오 건강도
          </p>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-4xl font-black" style={{ color: statusColor }}>{statusKo}</span>
            <span className="text-[13px] px-2 py-0.5 rounded font-bold" style={{ background: `${regColor}18`, color: regColor, border: `1px solid ${regColor}33` }}>
              시장 {REGIME_LABEL[regime] ?? regime}
            </span>
            {(detail.critical_count ?? 0) > 0 && (
              <span className="text-[13px] px-2 py-0.5 rounded font-bold" style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444433" }}>
                심각 {detail.critical_count}건
              </span>
            )}
            {(detail.warning_count ?? 0) > 0 && (
              <span className="text-[13px] px-2 py-0.5 rounded font-bold" style={{ background: "#f9731618", color: "#f97316", border: "1px solid #f9731633" }}>
                경고 {detail.warning_count}건
              </span>
            )}
          </div>
          <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>{statusDesc}</p>
          <p className="text-[12px] mt-2" style={{ color: "var(--text-faint)" }}>{detail.date} 기준</p>
        </div>

        {/* 핵심 수치 3개 */}
        <div className="flex flex-col gap-2">
          {/* 투자 비중 */}
          <div className="flex-1 rounded-xl p-3" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between mb-1">
              <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>현재 투자 비중</p>
              <InfoTooltip content="전체 자산 중 주식에 투자된 비율입니다. 시장 체제에 따라 권장 비중이 다릅니다." />
            </div>
            <div className="flex items-end gap-2">
              <span className="text-2xl font-black text-white">{investedPct}%</span>
              <span className="text-[12px] mb-0.5" style={{ color: cashPct > 50 ? "#39ff8f" : "var(--text-muted)" }}>현금 {cashPct}%</span>
            </div>
            <div className="mt-1.5 h-1.5 rounded-full" style={{ background: "var(--bg-inset)" }}>
              <div className="h-full rounded-full" style={{ width: `${investedPct}%`, background: investedPct > recPct + 10 ? "#f97316" : "#39ff8f" }} />
            </div>
            <p className="text-[12px] mt-1" style={{ color: "var(--text-faint)" }}>권장 {recPct}% (시장 {REGIME_LABEL[regime]} 기준)</p>
          </div>

          {/* 하루 최대 예상 손실 */}
          <div className="flex-1 rounded-xl p-3" style={{ background: "var(--bg-card)", border: `1px solid ${varWarning ? "#ef444433" : "var(--border)"}` }}>
            <div className="flex items-center justify-between mb-1">
              <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>하루 최대 예상 손실</p>
              <InfoTooltip content="95% 확률로 하루 동안 이 금액 이상은 잃지 않는다는 추정치입니다. (VaR 95%)" />
            </div>
            <p className="text-2xl font-black" style={{ color: varWarning ? "#ef4444" : "#facc15" }}>
              {detail.var_usd ? `-${usd(detail.var_usd)}` : varPct > 0 ? `-${varPct.toFixed(2)}%` : "—"}
            </p>
            <p className="text-[12px] mt-1" style={{ color: varWarning ? "#ef4444" : "var(--text-faint)" }}>
              {varWarning ? "⚠ 리스크 한도 초과 (1.5%)" : "리스크 한도 내 정상"}
            </p>
          </div>
        </div>
      </div>

      {/* ── 2. 알림 (있을 때만) ── */}
      {alerts.length > 0 && (
        <div className="bg-card rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <span style={{ color: "#f97316" }}>⚠</span>
            <h2 className="stat-label">지금 확인해야 할 것들</h2>
            <span className="ml-auto text-[12px]" style={{ color: "var(--text-muted)" }}>{alerts.length}건</span>
          </div>
          <div className="space-y-2">
            {alerts.map((a: any) => {
              const lvlColor = a.level === "CRITICAL" ? "#ef4444" : a.level === "WARNING" ? "#f97316" : "#60a5fa";
              const lvlKo    = a.level === "CRITICAL" ? "심각" : a.level === "WARNING" ? "경고" : "참고";
              return (
                <div key={a.id} className="flex items-start gap-3 rounded-lg p-3"
                  style={{ background: `${lvlColor}0d`, border: `1px solid ${lvlColor}33` }}>
                  <span className="shrink-0 text-[12px] font-bold px-2 py-0.5 rounded mt-0.5"
                    style={{ background: `${lvlColor}18`, color: lvlColor }}>{lvlKo}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-semibold text-white">
                      {a.ticker && <span className="mr-2" style={{ color: lvlColor }}>{a.ticker}</span>}
                      {a.message}
                    </p>
                    <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                      {a.category} · 현재값 {typeof a.value === "number" ? (Math.abs(a.value) < 1 ? pct(a.value) : a.value.toFixed(2)) : a.value}
                      {a.threshold != null && ` / 기준 ${typeof a.threshold === "number" ? (Math.abs(a.threshold) < 1 ? pct(a.threshold) : a.threshold.toFixed(2)) : a.threshold}`}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 3. 보유 종목 현황 + 섹터 분산 ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* 보유 종목별 비중 & 손익 */}
        {positions.length > 0 && (
          <div className="md:col-span-2 bg-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="stat-label">보유 종목 현황</h2>
              <InfoTooltip content="각 종목의 포트폴리오 내 비중과 현재 손익률입니다." />
              <span className="ml-auto text-[12px]" style={{ color: "var(--text-muted)" }}>
                투자 {investedPct}% · 현금 {cashPct}%
              </span>
            </div>
            <div className="space-y-1.5">
              {positions.map((p: any) => {
                const barW = Math.round((p.value / maxPosVal) * 100);
                const pnlC = p.pnl_pct >= 0 ? "#39ff8f" : "#ef4444";
                return (
                  <div key={p.symbol} className="flex items-center gap-2">
                    <span className="w-6 text-[12px] font-black text-center rounded shrink-0"
                      style={{ background: "#39ff8f22", color: "#39ff8f" }}>{p.grade}</span>
                    <span className="w-14 text-[13px] font-bold text-white shrink-0">{p.symbol}</span>
                    <div className="flex-1 h-5 rounded overflow-hidden" style={{ background: "var(--bg-inset)" }}>
                      <div className="h-full rounded flex items-center px-2"
                        style={{ width: `${barW}%`, background: "#39ff8f1a", minWidth: 4 }}>
                        <span className="text-[12px] font-bold" style={{ color: "#39ff8f" }}>
                          {Math.round((p.weight_pct ?? 0) * 100)}%
                        </span>
                      </div>
                    </div>
                    <span className="text-[13px] w-16 text-right shrink-0 font-bold" style={{ color: pnlC }}>
                      {pct(p.pnl_pct)}
                    </span>
                    <span className="text-[12px] w-16 text-right shrink-0" style={{ color: "var(--text-muted)" }}>
                      {usd(p.value)}
                    </span>
                  </div>
                );
              })}
              <div className="flex items-center gap-2 pt-1 mt-1" style={{ borderTop: "1px solid var(--border)" }}>
                <span className="w-6 shrink-0" />
                <span className="w-14 text-[13px] font-bold shrink-0" style={{ color: "var(--text-muted)" }}>CASH</span>
                <div className="flex-1 h-5 rounded overflow-hidden" style={{ background: "var(--bg-inset)" }}>
                  <div className="h-full rounded" style={{ width: `${cashPct}%`, background: "#ffffff0a" }} />
                </div>
                <span className="text-[13px] w-16 text-right shrink-0" style={{ color: "var(--text-muted)" }}>{cashPct}%</span>
                <span className="text-[12px] w-16 text-right shrink-0" style={{ color: "var(--text-muted)" }}>
                  {usd(detail.cash_value ?? 0)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* 섹터 분산 */}
        {sectors.length > 0 && (
          <div className="bg-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="stat-label">섹터 분산도</h2>
              <InfoTooltip content="한 섹터에 40% 이상 집중되면 분산 효과가 줄어듭니다." />
            </div>
            <div className="space-y-2">
              {sectors.map((s: any) => {
                const wPct   = Math.round(s.weight_pct * 100);
                const isHigh = wPct >= 40;
                const color  = isHigh ? "#f97316" : "#39ff8f";
                const barW   = Math.round((s.weight_pct / maxSector) * 100);
                return (
                  <div key={s.sector}>
                    <div className="flex justify-between text-[12px] mb-0.5">
                      <span style={{ color: isHigh ? "#f97316" : "var(--text-secondary)" }}>
                        {isHigh && "⚠ "}{s.sector}
                      </span>
                      <span style={{ color: isHigh ? "#f97316" : "var(--text-muted)" }}>{wPct}%</span>
                    </div>
                    <div className="h-1.5 rounded-full" style={{ background: "var(--bg-inset)" }}>
                      <div className="h-full rounded-full" style={{ width: `${barW}%`, background: color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── 4. 같이 움직이는 종목 + 종목별 리스크 기여 ── */}
      <div className="grid grid-cols-2 gap-3">
        {/* 상관관계 */}
        <div className="bg-card rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="stat-label">같이 움직이는 종목 쌍</h2>
            <InfoTooltip content="상관계수가 높을수록 두 종목이 같은 방향으로 움직입니다. 고상관 종목을 여러 개 보유하면 분산 효과가 줄어듭니다." />
          </div>
          <p className="text-[12px] mb-3" style={{ color: "var(--text-faint)" }}>상관계수 0.7 이상인 종목 쌍 (한쪽이 하락하면 다른쪽도 하락할 가능성 ↑)</p>
          {corrPairs.length === 0 ? (
            <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>✓ 고상관 종목 쌍 없음 — 분산이 잘 되어 있습니다</p>
          ) : (
            <div className="space-y-1.5">
              {corrPairs.slice(0, 8).map((pair: any, i: number) => {
                const absC  = Math.abs(pair.corr);
                const color = absC >= 0.9 ? "#ef4444" : absC >= 0.8 ? "#f97316" : "#facc15";
                const label = absC >= 0.9 ? "매우 강함" : absC >= 0.8 ? "강함" : "보통";
                return (
                  <div key={i} className="flex items-center justify-between rounded-lg px-3 py-2"
                    style={{ background: "var(--bg-inset)", border: `1px solid ${color}33` }}>
                    <div>
                      <span className="text-[13px] font-bold text-white">{pair.sym_a} ↔ {pair.sym_b}</span>
                      <span className="ml-2 text-[12px]" style={{ color: "var(--text-faint)" }}>동반 하락 위험</span>
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-black" style={{ color }}>{pair.corr.toFixed(2)}</span>
                      <span className="ml-1.5 text-[12px]" style={{ color }}>{label}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Component VaR */}
        {compVar.length > 0 && (
          <div className="bg-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="stat-label">종목별 리스크 기여도</h2>
              <InfoTooltip content="포트폴리오 전체 위험 중 각 종목이 기여하는 비중입니다. 막대가 길수록 해당 종목 때문에 포트폴리오가 더 위험해집니다." />
            </div>
            <p className="text-[12px] mb-3" style={{ color: "var(--text-faint)" }}>막대가 길수록 이 종목이 내 포트폴리오 리스크를 많이 올리고 있습니다</p>
            <div className="space-y-1.5">
              {compVar.map((c: any) => {
                const barW = Math.round((Math.abs(c.cvar_pct) / maxCompVar) * 100);
                return (
                  <div key={c.symbol} className="flex items-center gap-2">
                    <span className="w-14 text-[13px] font-bold text-white shrink-0">{c.symbol}</span>
                    <div className="flex-1 h-4 rounded overflow-hidden" style={{ background: "var(--bg-inset)" }}>
                      <div className="h-full rounded" style={{ width: `${barW}%`, background: "#ef444430" }} />
                    </div>
                    <span className="text-[12px] w-14 text-right shrink-0" style={{ color: "#ef4444" }}>
                      {pct(c.cvar_pct)}
                    </span>
                    <span className="text-[12px] w-16 text-right shrink-0" style={{ color: "var(--text-muted)" }}>
                      -{usd(Math.abs(c.cvar_usd))}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── 5. 종목별 낙폭 분석 ── */}
      {cdarTable.length > 0 && (
        <div className="bg-card rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="stat-label">종목별 낙폭 분석</h2>
            <InfoTooltip content="CDAR: 최근 60일 최대 낙폭 / CVaR: 최악 5% 상황 평균 손실 / 현재 낙폭: 고점 대비 현재 하락폭" />
            <span className="ml-auto text-[12px]" style={{ color: "var(--text-muted)" }}>최근 60일 기준</span>
          </div>
          <p className="text-[12px] mb-3" style={{ color: "var(--text-faint)" }}>현재 낙폭이 크거나 최악 손실이 큰 종목은 비중 축소를 고려하세요</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {[
                    { h: "종목", tip: null },
                    { h: "최대 낙폭 (60일)", tip: "최근 60일 중 가장 크게 떨어진 폭" },
                    { h: "최악 손실 (CVaR)", tip: "최악 5% 시나리오에서의 평균 손실" },
                    { h: "역대 최대 낙폭", tip: "보유 기간 중 가장 크게 떨어진 폭" },
                    { h: "현재 낙폭", tip: "고점 대비 현재 얼마나 내려왔는지" },
                  ].map(({ h, tip }) => (
                    <th key={h} className="px-3 py-2 text-left stat-label">
                      <span className="flex items-center gap-1">
                        {h}{tip && <InfoTooltip content={tip} />}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cdarTable.map((r: any) => {
                  const ddColor = r.current_dd < -0.1 ? "#ef4444" : r.current_dd < -0.05 ? "#f97316" : r.current_dd >= 0 ? "#39ff8f" : "var(--text-secondary)";
                  return (
                    <tr key={r.symbol} style={{ borderBottom: "1px solid var(--border-dim)" }}>
                      <td className="px-3 py-2.5 font-bold text-white">{r.symbol}</td>
                      <td className="px-3 py-2.5 font-semibold" style={{ color: "#ef4444" }}>{pct(r.cdar)}</td>
                      <td className="px-3 py-2.5" style={{ color: "#f97316" }}>{pct(r.cvar)}</td>
                      <td className="px-3 py-2.5" style={{ color: "var(--text-secondary)" }}>{pct(r.max_dd)}</td>
                      <td className="px-3 py-2.5 font-bold" style={{ color: ddColor }}>{pct(r.current_dd)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <PositionCalculator currency="USD" />
    </div>
  );
}
