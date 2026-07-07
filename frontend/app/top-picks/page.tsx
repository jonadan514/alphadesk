"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";
import { SECTOR_TO_ETF } from "@/src/lib/constants";

const ACTION_COLOR: Record<string, string> = {
  BUY: "#39ff8f", "SMALL BUY": "#22c55e", WATCH: "#facc15", HOLD: "#9ca3af", SKIP: "#4b5563",
};

// 파이프라인 데이터가 문자열 숫자(json default=str)나 비정형(GPT 출력)일 수 있어 방어적으로 변환
function num(v: unknown): number | null {
  if (typeof v === "number") return isFinite(v) ? v : null;
  if (typeof v === "string" && v.trim() !== "" && !isNaN(Number(v))) return Number(v);
  return null;
}
function arr(v: unknown): string[] {
  // AI 프롬프트가 catalysts/bear_cases를 {point, evidence} 객체 배열로 요구하므로
  // 객체면 point(+evidence)를 추출한다. 문자열 배열·단일 문자열도 허용.
  if (Array.isArray(v)) {
    return v
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const o = item as Record<string, unknown>;
          const point = typeof o.point === "string" ? o.point
            : typeof o.text === "string" ? o.text
            : typeof o.title === "string" ? o.title : "";
          const evidence = typeof o.evidence === "string" ? o.evidence : "";
          return [point, evidence].filter(Boolean).join(" ").trim();
        }
        return "";
      })
      .filter((s) => s.length > 0);
  }
  if (typeof v === "string" && v.trim()) return [v];
  return [];
}

function SectorBadge({ sector, leadingKeys, laggingKeys }: {
  sector: string;
  leadingKeys: string[];
  laggingKeys: string[];
}) {
  if (leadingKeys.includes(sector)) {
    return (
      <span className="text-[12px] font-bold px-1.5 py-0.5 rounded"
        style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
        ↑ LEADING
      </span>
    );
  }
  if (laggingKeys.includes(sector)) {
    return (
      <span className="text-[12px] font-bold px-1.5 py-0.5 rounded"
        style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444433" }}>
        ↓ LAGGING
      </span>
    );
  }
  return null;
}

function PickDetailModal({ pick, market, aiMap, onClose }: {
  pick: any;
  market: string;
  aiMap: Record<string, any>;
  onClose: () => void;
}) {
  const isKR  = market === "KR";
  const ai    = aiMap[pick.symbol] ?? aiMap[pick.name] ?? null;
  const color = pick.action === "BUY" ? "#39ff8f" : pick.action === "WATCH" ? "#facc15" : "#9ca3af";

  const rsRaw = num(pick.relative_strength);
  const factors = [
    { label: "기술 (Technical)",        val: num(pick.technical) },
    { label: "펀더멘털 (Fundamental)",  val: num(pick.fundamental) },
    ...(isKR ? [] : [{ label: "애널리스트 (Analyst)", val: num(pick.analyst) }]),
    { label: isKR ? "RS vs KOSPI" : "RS vs SPY",     val: rsRaw != null
        ? rsRaw * (Math.abs(rsRaw) < 2 ? 100 : 1) : null },
    { label: "거래량 (Volume)",         val: num(pick.volume) },
    ...(isKR ? [] : [{ label: "기관 (Institutional)",  val: num(pick.institutional) }]),
  ].filter((f) => f.val != null);

  const curPrice   = num(pick.current_price) ?? num(pick.cur_price);
  const targetUS   = num(pick.target_price);
  const targetAI   = num(ai?.target_price);
  const pct52      = num(pick.pct_from_52h);
  const compScore  = num(pick.composite_score);
  const catalysts  = arr(ai?.catalysts);
  const bearCases  = arr(ai?.bear_cases);
  const confidence = num(ai?.confidence);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl overflow-hidden"
        style={{ background: "#1c1c1c", border: `1.5px solid ${color}44`, maxHeight: "85vh", overflowY: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 flex items-start gap-4" style={{ background: "#131313", borderBottom: `1px solid ${color}22` }}>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-0.5">
              {pick.name
                ? <><span className="text-xl font-black text-white">{pick.name}</span>
                    <span className="text-[13px] font-mono" style={{ color: "var(--text-muted)" }}>{pick.symbol}</span></>
                : <span className="text-xl font-black text-white">{pick.symbol}</span>
              }
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}>{pick.action}</span>
              <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>Grade {pick.grade}</span>
              <span className="text-[12px] text-[#6b7280]">{pick.sector}</span>
            </div>
          </div>
          <div className="text-center">
            <p className="text-2xl font-black" style={{ color: "#39ff8f" }}>{compScore?.toFixed(1) ?? "—"}</p>
            <p className="text-[12px] text-[#6b7280]">종합 점수</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-white text-lg font-bold">✕</button>
        </div>

        <div className="px-5 py-4 space-y-3">
          {/* 가격 정보 */}
          {(curPrice != null || targetUS != null || targetAI != null) && (
            <div className="grid grid-cols-2 gap-3">
              {curPrice != null && (
                <div className="rounded-lg p-3" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
                  <p className="text-[12px] text-[#6b7280] mb-0.5">현재가</p>
                  <p className="text-lg font-black text-white">
                    {isKR ? `₩${curPrice.toLocaleString()}` : `$${curPrice.toFixed(2)}`}
                  </p>
                  {isKR && pct52 != null && (
                    <p className="text-[12px] mt-0.5" style={{ color: pct52 > -10 ? "#facc15" : "#9ca3af" }}>
                      52주 고점 대비 {pct52 > 0 ? "+" : ""}{pct52.toFixed(1)}%
                    </p>
                  )}
                </div>
              )}
              {isKR && targetAI != null && (
                <div className="rounded-lg p-3" style={{ background: "var(--bg-inset)", border: "1px solid #39ff8f22" }}>
                  <p className="text-[12px] text-[#6b7280] mb-0.5">AI 목표가</p>
                  <p className="text-lg font-black" style={{ color: "#39ff8f" }}>₩{targetAI.toLocaleString()}</p>
                  {curPrice != null && curPrice > 0 && (
                    <p className="text-[12px] mt-0.5" style={{ color: "#39ff8f" }}>
                      {((targetAI - curPrice) / curPrice) * 100 >= 0 ? "+" : ""}
                      {(((targetAI - curPrice) / curPrice) * 100).toFixed(1)}% 상승여력
                    </p>
                  )}
                </div>
              )}
              {!isKR && targetUS != null && (
                <div className="rounded-lg p-3" style={{ background: "var(--bg-inset)", border: "1px solid #39ff8f22" }}>
                  <p className="text-[12px] text-[#6b7280] mb-0.5">목표가</p>
                  <p className="text-lg font-black" style={{ color: "#39ff8f" }}>${targetUS.toFixed(2)}</p>
                  {curPrice != null && curPrice > 0 && (
                    <p className="text-[12px] mt-0.5" style={{ color: "#39ff8f" }}>
                      {((targetUS - curPrice) / curPrice) * 100 >= 0 ? "+" : ""}
                      {(((targetUS - curPrice) / curPrice) * 100).toFixed(1)}% 상승여력
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* KR 펀더멘털 지표 */}
          {isKR && (pick.per != null || pick.pbr != null || pick.roe != null || pick.dividend_yield != null) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { label: "PER", val: pick.per != null ? `${pick.per}x` : null },
                { label: "PBR", val: pick.pbr != null ? `${pick.pbr}x` : null },
                { label: "ROE", val: pick.roe != null ? `${pick.roe}%` : null },
                { label: "배당", val: pick.dividend_yield != null ? `${pick.dividend_yield}%` : null },
              ].filter(f => f.val).map(({ label, val }) => (
                <div key={label} className="rounded-lg p-2 text-center" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
                  <p className="text-[12px] text-[#6b7280]">{label}</p>
                  <p className="text-sm font-black text-white">{val}</p>
                </div>
              ))}
            </div>
          )}

          {/* Lynch/O'Neil 핵심 지표: PEG + EPS 성장 + 52주 고점 */}
          {(num(pick.peg_ratio) != null || pct52 != null || num(pick.earnings_growth) != null) && (() => {
            const pegVal = num(pick.peg_ratio);
            const pegColor = pegVal == null ? "#6b7280" : (isKR ? pegVal < 0.7 : pegVal < 1.0) ? "#39ff8f" : pegVal < 1.5 ? "#facc15" : "#ef4444";
            const peg52Val = pct52;
            const peg52Color = peg52Val == null ? "#6b7280" : peg52Val > -5 ? "#39ff8f" : peg52Val > -15 ? "#facc15" : "#ef4444";
            const egVal = num(pick.earnings_growth);
            const egColor = egVal == null ? "#6b7280" : egVal >= 25 ? "#39ff8f" : egVal >= 10 ? "#facc15" : "#ef4444";
            return (
              <div>
                <p className="text-[12px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "#6e6e6e" }}>
                  Lynch / O'Neil 지표
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {pegVal != null && (
                    <div className="rounded-lg p-2 text-center" style={{ background: "var(--bg-inset)", border: `1px solid ${pegColor}33` }}>
                      <p className="text-[12px]" style={{ color: "#6e6e6e" }}>PEG 비율</p>
                      <p className="text-sm font-black" style={{ color: pegColor }}>{pegVal.toFixed(2)}</p>
                      <p className="text-[12px]" style={{ color: pegColor }}>{(isKR ? pegVal < 0.7 : pegVal < 1.0) ? "Lynch ✓" : "주의"}</p>
                    </div>
                  )}
                  {egVal != null && (
                    <div className="rounded-lg p-2 text-center" style={{ background: "var(--bg-inset)", border: `1px solid ${egColor}33` }}>
                      <p className="text-[12px]" style={{ color: "#6e6e6e" }}>EPS 성장</p>
                      <p className="text-sm font-black" style={{ color: egColor }}>{egVal > 0 ? "+" : ""}{egVal.toFixed(1)}%</p>
                      <p className="text-[12px]" style={{ color: egColor }}>{egVal >= 25 ? "O'Neil ✓" : egVal >= 0 ? "성장중" : "역성장"}</p>
                    </div>
                  )}
                  {peg52Val != null && (
                    <div className="rounded-lg p-2 text-center" style={{ background: "var(--bg-inset)", border: `1px solid ${peg52Color}33` }}>
                      <p className="text-[12px]" style={{ color: "#6e6e6e" }}>52주 고점</p>
                      <p className="text-sm font-black" style={{ color: peg52Color }}>{peg52Val > 0 ? "+" : ""}{peg52Val.toFixed(1)}%</p>
                      <p className="text-[12px]" style={{ color: peg52Color }}>{peg52Val > -5 ? "돌파권" : peg52Val > -15 ? "조정중" : "하락중"}</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* 팩터 점수 */}
          {factors.length > 0 && (
            <div>
              <p className="text-[12px] font-bold uppercase tracking-widest text-[#6b7280] mb-2">팩터 점수</p>
              <div className="space-y-1.5">
                {factors.map(({ label, val }) => {
                  const score = Math.min(100, Math.max(0, val ?? 0));
                  const fc = score >= 70 ? "#39ff8f" : score >= 50 ? "#facc15" : "#ef4444";
                  return (
                    <div key={label} className="flex items-center gap-2">
                      <span className="text-[12px] w-36 shrink-0" style={{ color: "var(--text-muted)" }}>{label}</span>
                      <div className="flex-1 h-1.5 rounded-full" style={{ background: "var(--bg-inset)" }}>
                        <div className="h-1.5 rounded-full" style={{ width: `${score}%`, background: fc }} />
                      </div>
                      <span className="text-[12px] w-8 text-right font-mono font-bold" style={{ color: fc }}>{score.toFixed(0)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* AI thesis */}
          {ai && (
            <div className="space-y-2">
              <p className="text-[12px] font-bold uppercase tracking-widest text-[#6b7280]">AI 분석</p>
              {ai.thesis && (
                <p className="text-[12px] leading-relaxed" style={{ color: "#c0c0c0" }}>{ai.thesis}</p>
              )}
              <div className="grid grid-cols-2 gap-3">
                {catalysts.length > 0 && (
                  <div>
                    <p className="text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#39ff8f" }}>상승 촉매</p>
                    <ul className="space-y-0.5">
                      {catalysts.slice(0, 3).map((c, i) => (
                        <li key={i} className="text-[12px] flex gap-1" style={{ color: "#a8a8a8" }}>
                          <span style={{ color: "#39ff8f" }}>▲</span>{c}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {bearCases.length > 0 && (
                  <div>
                    <p className="text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#ef4444" }}>하락 리스크</p>
                    <ul className="space-y-0.5">
                      {bearCases.slice(0, 3).map((b, i) => (
                        <li key={i} className="text-[12px] flex gap-1" style={{ color: "#a8a8a8" }}>
                          <span style={{ color: "#ef4444" }}>▼</span>{b}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              {confidence != null && (
                <div>
                  <div className="flex justify-between text-[12px] text-[#6b7280] mb-0.5">
                    <span>AI 신뢰도</span><span>{Math.round(confidence)}%</span>
                  </div>
                  <div className="h-1 rounded-full" style={{ background: "#282828" }}>
                    <div className="h-1 rounded-full" style={{ width: `${Math.min(100, Math.max(0, confidence))}%`, background: "#39ff8f" }} />
                  </div>
                </div>
              )}
            </div>
          )}

          {!ai && (
            <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>AI 분석 데이터 없음 — 다음 일간 분석 실행 후 업데이트됩니다.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TopPicksPage() {
  const { market } = useMarket();
  const [picks, setPicks]             = useState<any[]>([]);
  const [report, setReport]           = useState<any>({});
  const [leadingKeys, setLeadingKeys] = useState<string[]>([]);
  const [laggingKeys, setLaggingKeys] = useState<string[]>([]);
  const [cycleLabel, setCycleLabel]   = useState<string>("");
  const [loading, setLoading]         = useState(true);
  const [selectedPick, setSelectedPick] = useState<any>(null);
  const [aiMap, setAiMap]             = useState<Record<string, any>>({});
  const [myWatch, setMyWatch]         = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch("/api/watchlist/my")
      .then((r) => r.json())
      .then((rows) => {
        if (Array.isArray(rows)) {
          setMyWatch(new Set(rows.map((w: any) => `${w.market}:${w.symbol}`)));
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setPicks([]);

    if (market === "KR") {
      Promise.allSettled([
        fetch("/api/data/kr/reports?limit=1").then((r) => r.json()),
        fetch("/api/data/kr/sector").then((r) => r.json()),
        fetch("/api/data/kr/ai-summaries").then((r) => r.json()),
      ]).then(([reportsRes, sectorRes, aiRes]) => {
        if (reportsRes.status === "fulfilled") {
          const r = reportsRes.value[0] ?? {};
          setReport(r);
          setPicks(r.picks ?? []);
        }
        if (sectorRes.status === "fulfilled" && sectorRes.value) {
          const s = sectorRes.value;
          setLeadingKeys((s.leading ?? []).map((l: any) => l.sector));
          setLaggingKeys((s.lagging ?? []).map((l: any) => l.sector));
          setCycleLabel(s.cycle_label ?? "");
        }
        if (aiRes.status === "fulfilled") {
          const summaries: any[] = aiRes.value?.summaries ?? (Array.isArray(aiRes.value) ? aiRes.value : []);
          const map: Record<string, any> = {};
          summaries.forEach((s: any) => { if (s.ticker) map[s.ticker] = s; });
          setAiMap(map);
        }
        setLoading(false);
      });
    } else {
      Promise.allSettled([
        fetch("/api/data/reports?limit=1").then((r) => r.json()),
        fetch("/api/data/sector").then((r) => r.json()),
        fetch("/api/data/ai-summaries").then((r) => r.json()),
      ]).then(([reportsRes, sectorRes, aiRes]) => {
        if (reportsRes.status === "fulfilled") {
          const r = reportsRes.value[0] ?? {};
          setReport(r);
          setPicks(r.picks ?? []);
        }
        if (sectorRes.status === "fulfilled" && sectorRes.value) {
          const s = sectorRes.value;
          setLeadingKeys((s.leading ?? []).map((l: any) => l.ticker));
          setLaggingKeys((s.lagging ?? []).map((l: any) => l.ticker));
          setCycleLabel(s.cycle_label ?? "");
        }
        if (aiRes.status === "fulfilled") {
          const summaries: any[] = aiRes.value?.summaries ?? (Array.isArray(aiRes.value) ? aiRes.value : []);
          const map: Record<string, any> = {};
          summaries.forEach((s: any) => { if (s.ticker) map[s.ticker] = s; });
          setAiMap(map);
        }
        setLoading(false);
      });
    }
  }, [market]);

  // For US: convert sector → ETF key for badge lookup
  function getSectorKey(sector: string): string {
    return market === "KR" ? sector : (SECTOR_TO_ETF[sector] ?? sector);
  }

  const isKR = market === "KR";
  const hasSignal = leadingKeys.length > 0 || laggingKeys.length > 0;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="bg-card rounded-lg p-3">
        <div className="flex items-center gap-3 mb-1">
          <span className="text-accent">★</span>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-white">
              <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"} 상위 {picks.length}
            </h1>
            <InfoTooltip content={
              isKR
                ? "기술·펀더멘털·KOSPI 대비 RS·거래량 4가지 팩터를 가중 합산한 복합 점수 기준 상위 KOSPI 종목입니다."
                : "기술·펀더멘털·애널리스트·상대강도(RS)·거래량·기관 6가지 팩터를 가중 합산한 복합 점수 기준 상위 종목입니다."
            } />
          </div>
        </div>
        <p className="text-[12px] text-[#6b7280]">
          {isKR ? "KOSPI 4팩터 스크리닝" : "기관 자금흐름 & AI 스코어링"} · {picks.length}개
          {report.analysis_date && <span className="ml-2">{report.analysis_date}</span>}
        </p>

        {hasSignal && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {cycleLabel && (
              <span className="text-[12px] font-semibold" style={{ color: "var(--text-muted)" }}>
                현재 사이클 · <span className="text-white">{cycleLabel}</span>
              </span>
            )}
            {leadingKeys.length > 0 && (
              <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
                선행:&nbsp;
                {leadingKeys.map(k => (
                  <span key={k} className="font-bold" style={{ color: "#39ff8f" }}>{k} </span>
                ))}
              </span>
            )}
            {laggingKeys.length > 0 && (
              <span className="text-[12px]" style={{ color: "var(--text-muted)" }}>
                후행:&nbsp;
                {laggingKeys.map(k => (
                  <span key={k} className="font-bold" style={{ color: "#ef4444" }}>{k} </span>
                ))}
              </span>
            )}
          </div>
        )}
      </div>

      {loading && <p className="text-sm text-[#6b7280]">로딩 중…</p>}
      {!loading && picks.length === 0 && (
        <p className="text-sm text-[#6b7280]">
          데이터 없음. GitHub → Actions → Daily Analysis 실행 후 재확인하세요.
        </p>
      )}

      {/* 종목 상세 모달 */}
      {selectedPick && (
        <PickDetailModal
          pick={selectedPick}
          market={market}
          aiMap={aiMap}
          onClose={() => setSelectedPick(null)}
        />
      )}

      {picks.length > 0 && (
        <div className="bg-card rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ borderBottom: "1px solid #2a2a2a" }}>
                {[
                  { label: "#",        tip: null },
                  { label: "종목",     tip: null },
                  { label: "등급",     tip: "A = 상위(80+), B = 70+, C = 60+, D = 50+, F = 이하" },
                  { label: "종합점수", tip: "0~100 복합 점수. 높을수록 복수 팩터에서 강세 신호." },
                  { label: "기술",     tip: "이동평균·RSI·MACD 기반 기술적 점수(0~100)" },
                  { label: "펀다",     tip: isKR ? "PER·PBR·ROE 기반 가치 점수(0~100)" : "EPS·PEG·ROE 기반 점수(0~100)" },
                  ...(isKR ? [] : [{ label: "애널리스트", tip: "목표주가 상승 여력·BUY 비율 합산(0~100)" }]),
                  { label: isKR ? "RS vs KOSPI" : "RS vs SPY", tip: "벤치마크 대비 초과 수익률" },
                  { label: "섹터",     tip: "현재 사이클에서 선행/후행 섹터 여부" },
                  { label: "액션",     tip: "BUY = 신규 진입 권고. WATCH = 관심 유지." },
                ].map(({ label, tip }) => (
                  <th key={label} className="px-3 py-3 text-left font-semibold uppercase tracking-wider" style={{ color: "#6e6e6e", fontSize: "10px" }}>
                    <span className="flex items-center gap-1">
                      {label}
                      {tip && <InfoTooltip content={tip} />}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {picks.map((p: any, i: number) => {
                const sectorKey = getSectorKey(p.sector ?? "");
                const isLeading = leadingKeys.includes(sectorKey);
                const isLagging = laggingKeys.includes(sectorKey);
                const rs = num(p.relative_strength);
                const rsDisplay = rs != null
                  ? `${rs >= 0 ? "+" : ""}${Math.abs(rs) < 2 ? (rs * 100).toFixed(1) : rs.toFixed(2)}%`
                  : "—";

                return (
                  <tr
                    key={p.symbol}
                    className="transition-colors cursor-pointer"
                    style={{
                      borderBottom: "1px solid #2e2e2e",
                      background: isLeading ? "#39ff8f04" : "transparent",
                    }}
                    onClick={() => setSelectedPick(p)}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#161616")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = isLeading ? "#39ff8f04" : "transparent")}
                  >
                    <td className="px-3 py-3 font-mono text-[#6b7280]">
                      {String(i + 1).padStart(2, "0")}
                    </td>
                    <td className="px-3 py-3">
                      {(() => {
                        const inWatch = myWatch.has(`${market}:${p.symbol}`);
                        const badge = inWatch && (
                          <span title="내 워치리스트에 담긴 종목"
                            className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                            style={{ background: "#60a5fa20", color: "#60a5fa", border: "1px solid #60a5fa40" }}>
                            🔖 워치
                          </span>
                        );
                        return p.name
                          ? <><div className="font-black text-white flex items-center gap-1.5">{p.name}{badge}</div>
                              <div className="text-[12px] font-mono" style={{ color: "var(--text-muted)" }}>{p.symbol}</div></>
                          : <div className="font-black text-white flex items-center gap-1.5">{p.symbol}{badge}</div>;
                      })()}
                      <div className="text-[12px]" style={{ color: "var(--text-faint)" }}>{p.sector}</div>
                    </td>
                    <td className="px-3 py-3">
                      <span className="px-2 py-0.5 rounded text-[13px] font-bold" style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
                        {p.grade}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-accent">{p.composite_score?.toFixed(1)}</span>
                        <div className="w-16 h-1 rounded-full" style={{ background: "#282828" }}>
                          <div className="h-1 rounded-full" style={{ width: `${p.composite_score ?? 0}%`, background: "#39ff8f" }} />
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3 font-mono text-white">{p.technical != null ? Math.round(p.technical) : "—"}</td>
                    <td className="px-3 py-3 font-mono text-white">{p.fundamental != null ? Math.round(p.fundamental) : "—"}</td>
                    {!isKR && (
                      <td className="px-3 py-3 font-mono text-white">{p.analyst != null ? Math.round(p.analyst) : "—"}</td>
                    )}
                    <td className="px-3 py-3 font-mono font-bold" style={{ color: "#39ff8f" }}>
                      {rsDisplay}
                    </td>
                    <td className="px-3 py-3">
                      <SectorBadge sector={sectorKey} leadingKeys={leadingKeys} laggingKeys={laggingKeys} />
                    </td>
                    <td className="px-3 py-3">
                      <span className="px-2 py-1 rounded text-[12px] font-bold"
                        style={{ background: `${ACTION_COLOR[p.action] ?? "#4b5563"}22`, color: ACTION_COLOR[p.action] ?? "#9ca3af", border: `1px solid ${ACTION_COLOR[p.action] ?? "#4b5563"}44` }}>
                        {p.action}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </div>
      )}
    </div>
  );
}
