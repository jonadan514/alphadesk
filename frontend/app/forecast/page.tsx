"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";

const DIR_COLOR = (d: string) => d === "bullish" ? "#39ff8f" : "#ef4444";
const DIR_LABEL = (d: string) => d === "bullish" ? "BULLISH" : "BEARISH";

function ProbBar({ prob, direction }: { prob: number; direction: string }) {
  const pct = Math.round(prob * 100);
  const color = DIR_COLOR(direction);
  return (
    <div>
      <div className="flex justify-between text-[12px] mb-1" style={{ color: "var(--text-muted)" }}>
        <span>상승 확률</span>
        <span style={{ color }}>{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: "#282828" }}>
        <div className="h-1.5 rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function KeyDriverRow({ driver }: { driver: any }) {
  const dColor = DIR_COLOR(driver.direction);
  const barW   = Math.round((driver.importance_pct ?? 0) * 100);
  return (
    <div className="py-1.5" style={{ borderBottom: "1px solid var(--border-dim)" }}>
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-semibold w-36 shrink-0 truncate" style={{ color: "var(--text-secondary)" }}>
          {driver.label ?? driver.name}
        </span>
        <span
          className="text-[12px] font-bold px-1.5 py-0.5 rounded shrink-0"
          style={{ background: `${dColor}18`, color: dColor, border: `1px solid ${dColor}33` }}
        >
          {DIR_LABEL(driver.direction)}
        </span>
        <div className="flex-1 h-1 rounded-full mx-1" style={{ background: "#282828" }}>
          <div className="h-1 rounded-full" style={{ width: `${barW}%`, background: dColor }} />
        </div>
        <span className="text-[12px] w-12 text-right shrink-0" style={{ color: "var(--text-muted)" }}>
          {driver.value?.toFixed(3)}
        </span>
      </div>
      {driver.desc && (
        <p className="text-[11px] mt-0.5 ml-0" style={{ color: "var(--text-faint, #4a4a4a)" }}>
          {driver.desc}
        </p>
      )}
    </div>
  );
}

function IndexCard({ title, data }: { title: string; data: any }) {
  if (!data?.direction) return (
    <div className="bg-card rounded-xl p-3">
      <h2 className="text-sm font-bold text-white mb-2">{title}</h2>
      <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>데이터 없음. 분석 실행 후 표시됩니다.</p>
    </div>
  );

  const color  = DIR_COLOR(data.direction);
  const pct    = Math.round((data.probability ?? 0.5) * 100);
  const cvPct  = data.cv_accuracy != null ? Math.round(data.cv_accuracy * 100) : null;
  const predRet = data.predicted_return ?? 0;

  return (
    <div className="bg-card rounded-xl p-3 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-white">{title}</h2>
        <span
          className="text-[12px] px-2 py-0.5 rounded font-bold"
          style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
        >
          {data.confidence} {pct}%
        </span>
      </div>

      {/* Direction */}
      <div className="flex items-center gap-2">
        <span className="text-xl" style={{ color }}>{data.direction === "bullish" ? "↑" : "↓"}</span>
        <span className="text-2xl font-black capitalize" style={{ color }}>
          {data.direction === "bullish" ? "강세" : "약세"}
        </span>
      </div>

      <ProbBar prob={data.probability ?? 0.5} direction={data.direction} />

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg p-3" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-1 mb-1">
            <p className="stat-label">예상 수익률</p>
            <InfoTooltip content="확률의 강도에 비례해 추정한 주간 기대 수익률입니다. 실제 수익률을 보장하지 않습니다." />
          </div>
          <p className="text-sm font-bold" style={{ color: predRet >= 0 ? "#39ff8f" : "#ef4444" }}>
            {predRet >= 0 ? "+" : ""}{(predRet * 100).toFixed(3)}%
          </p>
        </div>
        <div className="rounded-lg p-3" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-1 mb-1">
            <p className="stat-label">모델 정확도</p>
            <InfoTooltip content="TimeSeriesSplit 교차검증 방향 예측 정확도입니다. 50%는 랜덤 수준입니다." />
          </div>
          <p className="text-sm font-bold text-white">
            {cvPct != null ? `${cvPct}%` : `${pct}%`}
          </p>
        </div>
      </div>

      {/* Key Drivers */}
      {data.key_drivers?.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <p className="stat-label">KEY DRIVERS</p>
            <InfoTooltip content="모델이 이번 예측에서 가장 중요하게 참고한 피처들입니다. 막대 길이는 기여도, 색상은 방향을 나타냅니다." />
          </div>
          <div>
            {data.key_drivers.slice(0, 5).map((d: any, i: number) => (
              <KeyDriverRow key={i} driver={d} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ForecastPage() {
  const { market } = useMarket();
  const [data, setData]       = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setData(null);
    setHistory([]);

    if (market === "KR") {
      fetch("/api/data/kr/forecast").then(r => r.json()).then(d => { setData(d); setLoading(false); });
    } else {
      Promise.allSettled([
        fetch("/api/data/index-prediction").then(r => r.json()),
        fetch("/api/data/prediction-history").then(r => r.json()),
      ]).then(([predRes, histRes]) => {
        if (predRes.status === "fulfilled") setData(predRes.value);
        if (histRes.status === "fulfilled") setHistory(histRes.value ?? []);
        setLoading(false);
      });
    }
  }, [market]);

  const isKR = market === "KR";
  const spy = !isKR ? (data?.spy ?? (data?.direction ? data : null)) : null;
  const qqq = !isKR ? (data?.qqq ?? null) : null;

  const chartData = history.slice(0, 16).reverse().map((h: any) => ({
    date: h.date?.slice(5),
    spy:  h.spy?.probability ?? h.probability ?? null,
    qqq:  h.qqq?.probability ?? null,
  }));

  const spyCvPct  = spy?.cv_accuracy != null ? Math.round(spy.cv_accuracy * 100) : null;
  const qqqCvPct  = qqq?.cv_accuracy != null ? Math.round(qqq.cv_accuracy * 100) : null;
  const trainedAt = spy?.trained_at ?? "—";
  const featCount = spy?.feature_count ?? 27;

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
            <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
          </span>
          <h1 className="text-base font-bold text-white">지수 예측</h1>
          <InfoTooltip content={isKR
            ? "LightGBM 모델로 다음 주 KOSPI 방향(강세/약세)과 확률을 예측합니다. 15개 피처(KOSPI 기술 지표·환율·SPY 파급·KOSDAQ 브레드스) 기반입니다."
            : "LightGBM 모델로 다음 주 SPY/QQQ 방향(강세/약세)과 확률을 예측합니다."} />
        </div>
        <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          {isKR ? "KOSPI · 5일 전망 · LightGBM" : "SPY/QQQ · 5일 전망 · LightGBM"}
        </p>
      </div>

      {loading && <p className="text-sm" style={{ color: "var(--text-muted)" }}>로딩 중…</p>}

      {/* KR 예측 뷰 */}
      {isKR && !loading && (
        <div className="space-y-3">
          <IndexCard title="KOSPI" data={data} />
          {data?.direction && (
            <div className="bg-card rounded-xl p-3">
              <div className="flex items-center gap-2 mb-2">
                <p className="stat-label">MODEL INFO</p>
                <InfoTooltip content="모델 학습 정보 및 교차검증 정확도입니다." />
                <span className="ml-auto text-[12px]" style={{ color: "var(--text-faint)" }}>
                  {data.model_type === "lightgbm" ? "KOSPI · 5-day horizon · 15 features" : "Rule-based fallback"}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-4">
                <div>
                  <p className="stat-label mb-1">KOSPI CV ACC</p>
                  <p className="text-xl font-black" style={{ color: "#39ff8f" }}>
                    {data.cv_accuracy != null ? `${Math.round(data.cv_accuracy * 100)}%` : "—"}
                  </p>
                </div>
                <div>
                  <p className="stat-label mb-1">MODEL TYPE</p>
                  <p className="text-base font-bold text-white capitalize">{data.model_type ?? "—"}</p>
                </div>
                <div>
                  <p className="stat-label mb-1">TRAINED</p>
                  <p className="text-base font-bold text-white">{data.trained_at ?? "—"}</p>
                </div>
                <div>
                  <p className="stat-label mb-1">FEATURES</p>
                  <p className="text-xl font-black text-white">{data.feature_count ?? "—"}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* US 예측 뷰 */}
      {!isKR && !loading && (
        <div className="grid grid-cols-2 gap-4">
          <IndexCard title="SPY" data={spy} />
          <IndexCard title="QQQ" data={qqq} />
        </div>
      )}

      {/* Model Info (US only) */}
      {!isKR && spy && (
        <div className="bg-card rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <p className="stat-label">MODEL INFO</p>
            <InfoTooltip content="모델 학습 정보 및 교차검증 정확도입니다." />
            <span className="ml-auto text-[12px]" style={{ color: "var(--text-faint)" }}>SPY/QQQ · 5-day horizon</span>
          </div>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <p className="stat-label mb-1">SPY CV ACC</p>
              <p className="text-xl font-black" style={{ color: "#39ff8f" }}>
                {spyCvPct != null ? `${spyCvPct}%` : "—"}
              </p>
            </div>
            <div>
              <p className="stat-label mb-1">QQQ CV ACC</p>
              <p className="text-xl font-black" style={{ color: "#39ff8f" }}>
                {qqqCvPct != null ? `${qqqCvPct}%` : "—"}
              </p>
            </div>
            <div>
              <p className="stat-label mb-1">TRAINED</p>
              <p className="text-base font-bold text-white">{trainedAt}</p>
            </div>
            <div>
              <p className="stat-label mb-1">FEATURES</p>
              <p className="text-xl font-black text-white">{featCount}</p>
            </div>
          </div>
        </div>
      )}

      {/* History */}
      {(chartData.length > 0 || history.length > 0) && (
        <div className="bg-card rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <p className="stat-label">PREDICTION HISTORY</p>
            <InfoTooltip content="과거 예측 이력입니다. 16개 엔트리 · 0.5 = neutral" />
          </div>

          {chartData.length > 0 && (
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--text-muted)" }} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 9, fill: "var(--text-muted)" }} tickFormatter={v => `${Math.round(v * 100)}%`} />
                <Tooltip
                  formatter={(v: any) => `${Math.round(v * 100)}%`}
                  contentStyle={{ background: "#131313", border: "1px solid var(--border)", fontSize: 11, borderRadius: 10 }}
                />
                <ReferenceLine y={0.5} stroke="var(--border)" strokeDasharray="4 2" />
                <Line type="monotone" dataKey="spy" stroke="#39ff8f" strokeWidth={2} dot={false} name="SPY prob_up" connectNulls />
                {chartData.some(d => d.qqq != null) && (
                  <Line type="monotone" dataKey="qqq" stroke="#facc15" strokeWidth={2} dot={false} name="QQQ prob_up" connectNulls />
                )}
              </LineChart>
            </ResponsiveContainer>
          )}

          <table className="w-full text-[13px] mt-4">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["DATE", "SPY", "SPY PROB", "QQQ", "QQQ PROB", "MODEL ACC"].map(h => (
                  <th key={h} className="py-2 text-left stat-label">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 16).map((h: any) => {
                const s = h.spy ?? h;
                const q = h.qqq ?? null;
                const cvAcc = s.cv_accuracy != null ? Math.round(s.cv_accuracy * 100) : null;
                return (
                  <tr key={h.date} style={{ borderBottom: "1px solid var(--border-dim)" }}>
                    <td className="py-1.5" style={{ color: "var(--text-muted)" }}>{h.date}</td>
                    <td className="py-1.5 font-semibold" style={{ color: s.direction === "bullish" ? "#39ff8f" : "#ef4444" }}>
                      {s.direction === "bullish" ? "↑ UP" : "↓ DN"}
                    </td>
                    <td className="py-1.5 text-white">{s.probability != null ? `${Math.round(s.probability * 100)}%` : "—"}</td>
                    <td className="py-1.5 font-semibold" style={{ color: q?.direction === "bullish" ? "#39ff8f" : "#ef4444" }}>
                      {q ? (q.direction === "bullish" ? "↑ UP" : "↓ DN") : "—"}
                    </td>
                    <td className="py-1.5 text-white">{q?.probability != null ? `${Math.round(q.probability * 100)}%` : "—"}</td>
                    <td className="py-1.5 text-white">{cvAcc != null ? `${cvAcc}%` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
