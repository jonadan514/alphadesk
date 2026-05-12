"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";

interface DownloadItem {
  id: string;
  label: string;
  description: string;
  apiPath: string;
  filename: string;
  type: "json" | "csv";
}

const US_DOWNLOADS: DownloadItem[] = [
  {
    id: "sp500-list",
    label: "S&P 500 종목 리스트",
    description: "Wikipedia에서 파싱한 503개 S&P 500 종목 (Symbol, Security, GICS Sector)",
    apiPath: "/api/data/reports",
    filename: "sp500_list.csv",
    type: "csv",
  },
  {
    id: "smart-money-picks",
    label: "Smart Money Picks",
    description: "6-factor 가중 복합 점수 기준 상위 종목 (Grade, Action, 팩터별 점수)",
    apiPath: "/api/data/reports?limit=1",
    filename: "smart_money_picks.json",
    type: "json",
  },
  {
    id: "latest-report",
    label: "Latest Report",
    description: "최신 통합 분석 리포트 (Verdict, Regime, Gate, Picks 전체)",
    apiPath: "/api/data/reports?limit=1",
    filename: "latest_report.json",
    type: "json",
  },
  {
    id: "regime",
    label: "Market Regime",
    description: "5-sensor 시장 체제 스냅샷 (weighted_score, sensor_scores, macro_snapshot)",
    apiPath: "/api/data/regime",
    filename: "regime.json",
    type: "json",
  },
  {
    id: "prediction-history",
    label: "Prediction History",
    description: "날짜별 예측 이력 최대 100개 (direction, probability, confidence)",
    apiPath: "/api/data/prediction-history",
    filename: "prediction_history.json",
    type: "json",
  },
  {
    id: "gbm-predictions",
    label: "GBM Predictions",
    description: "LightGBM 예측 상위 종목 (pred_score, pred_rank)",
    apiPath: "/api/data/gbm-predictions",
    filename: "gbm_predictions.json",
    type: "json",
  },
];

const KR_DOWNLOADS: DownloadItem[] = [
  {
    id: "kr-picks",
    label: "KR BUY 추천 종목",
    description: "4-factor 복합 점수 기준 KOSPI 상위 종목 (grade, composite_score, sector, cur_price)",
    apiPath: "/api/data/kr/reports?limit=1",
    filename: "kr_picks.json",
    type: "json",
  },
  {
    id: "kr-regime",
    label: "KOSPI 시장 체제",
    description: "4-sensor KOSPI 체제 스냅샷 (trend, volatility, momentum, breadth, kospi_last)",
    apiPath: "/api/data/kr/regime",
    filename: "kr_regime.json",
    type: "json",
  },
  {
    id: "kr-market-gate",
    label: "KR 마켓 게이트",
    description: "rule-based 진입 신호 (GO / CAUTION / STOP) 및 근거",
    apiPath: "/api/data/kr/market-gate",
    filename: "kr_market_gate.json",
    type: "json",
  },
  {
    id: "kr-sector",
    label: "KR 섹터 분석",
    description: "KOSPI 섹터별 RS 점수, 사이클 위치, Leading/Lagging 분류",
    apiPath: "/api/data/kr/sector",
    filename: "kr_sector.json",
    type: "json",
  },
  {
    id: "kr-ai-summaries",
    label: "KR AI 분석 요약",
    description: "Gemini 2.5 Flash 생성 BUY 종목 투자 thesis, catalysts, bear cases",
    apiPath: "/api/data/kr/ai-summaries",
    filename: "kr_ai_summaries.json",
    type: "json",
  },
  {
    id: "kr-forecast",
    label: "KR 지수 방향 예측",
    description: "체제 기반 rule-based KOSPI 방향 확률 (bull_prob, bear_prob)",
    apiPath: "/api/data/kr/forecast",
    filename: "kr_forecast.json",
    type: "json",
  },
];

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export default function DownloadPage() {
  const { market } = useMarket();
  const [sizes, setSizes]     = useState<Record<string, number>>({});
  const [mtimes, setMtimes]   = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const DOWNLOADS = market === "KR" ? KR_DOWNLOADS : US_DOWNLOADS;
  const isKR = market === "KR";

  useEffect(() => {
    setSizes({});
    setMtimes({});
    DOWNLOADS.forEach((d) => {
      fetch(d.apiPath)
        .then((r) => r.text())
        .then((text) => {
          setSizes((p) => ({ ...p, [d.id]: new Blob([text]).size }));
          setMtimes((p) => ({ ...p, [d.id]: new Date().toLocaleString() }));
        })
        .catch(() => {});
    });
  }, [market]);

  async function handleDownload(item: DownloadItem) {
    setLoading((p) => ({ ...p, [item.id]: true }));
    try {
      const res  = await fetch(item.apiPath);
      const data = await res.json();
      const content = item.type === "csv"
        ? jsonToCsv(Array.isArray(data) ? data : [data])
        : JSON.stringify(data, null, 2);
      const mime = item.type === "csv" ? "text/csv" : "application/json";
      const blob = new Blob([content], { type: mime });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = item.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading((p) => ({ ...p, [item.id]: false }));
    }
  }

  function jsonToCsv(rows: Record<string, any>[]): string {
    if (!rows.length) return "";
    const flat = rows.map((r) => flattenObj(r));
    const keys = Array.from(new Set(flat.flatMap(Object.keys)));
    const header = keys.join(",");
    const body   = flat.map((r) =>
      keys.map((k) => {
        const v = r[k] ?? "";
        const s = String(v).replace(/"/g, '""');
        return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s}"` : s;
      }).join(",")
    );
    return [header, ...body].join("\n");
  }

  function flattenObj(obj: any, prefix = ""): Record<string, any> {
    return Object.entries(obj ?? {}).reduce<Record<string, any>>((acc, [k, v]) => {
      const key = prefix ? `${prefix}.${k}` : k;
      if (v && typeof v === "object" && !Array.isArray(v)) {
        Object.assign(acc, flattenObj(v, key));
      } else {
        acc[key] = Array.isArray(v) ? JSON.stringify(v) : v;
      }
      return acc;
    }, {});
  }

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
            <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
          </span>
          <h1 className="text-base font-bold text-white">다운로드</h1>
          <InfoTooltip content="최신 분석 결과물을 JSON 또는 CSV 형식으로 내려받습니다." />
        </div>
        <p className="text-[12px] text-[#6b7280]">분석 결과물을 JSON / CSV 형식으로 다운로드합니다.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {DOWNLOADS.map((item) => {
          const isJson = item.type === "json";
          const typeColor = isJson ? "#39ff8f" : "#facc15";
          return (
            <div
              key={item.id}
              className="flex flex-col rounded-lg p-5"
              style={{ background: "#131313", border: `1px solid ${typeColor}22` }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="rounded px-2 py-0.5 text-[12px] font-bold uppercase"
                  style={{ background: `${typeColor}22`, color: typeColor, border: `1px solid ${typeColor}44` }}
                >
                  {item.type}
                </span>
                <span className="text-[12px] text-[#6b7280] font-mono truncate">{item.filename}</span>
              </div>

              <h2 className="text-sm font-bold text-white mb-1">{item.label}</h2>
              <p className="flex-1 text-[13px] text-[#9ca3af] leading-relaxed mb-2">
                {item.description}
              </p>

              <div className="space-y-0.5 text-[12px] text-[#6b7280] mb-4">
                {sizes[item.id] && <p>크기: {formatBytes(sizes[item.id])}</p>}
                {mtimes[item.id] && <p>확인: {mtimes[item.id]}</p>}
              </div>

              <button
                onClick={() => handleDownload(item)}
                disabled={loading[item.id]}
                className="w-full rounded py-2 text-[13px] font-bold transition-colors"
                style={{
                  background: loading[item.id] ? "#1e1e1e" : `${typeColor}22`,
                  color: loading[item.id] ? "#6b7280" : typeColor,
                  border: `1px solid ${loading[item.id] ? "#2a2a2a" : `${typeColor}44`}`,
                  cursor: loading[item.id] ? "not-allowed" : "pointer",
                }}
              >
                {loading[item.id] ? "다운로드 중…" : "다운로드"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
