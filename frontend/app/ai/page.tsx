"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";

const REC_STYLE: Record<string, { bg: string; color: string }> = {
  BUY:  { bg: "#39ff8f22", color: "#39ff8f" },
  HOLD: { bg: "#facc1522", color: "#facc15" },
  SELL: { bg: "#ef444422", color: "#ef4444" },
};

function AISummaryCard({ summary, idx }: { summary: any; idx: number }) {
  const isFallback = summary._fallback === true || summary.confidence === 0;
  const [open, setOpen] = useState(!isFallback && idx < 3);
  const rec = isFallback
    ? { bg: "#2a2a2a", color: "#6e6e6e" }
    : (REC_STYLE[summary.recommendation] ?? { bg: "#2a2a2a", color: "#a8a8a8" });
  const conf = summary.confidence ?? 0;

  return (
    <div className="rounded-lg overflow-hidden" style={{
      background: "#1c1c1c",
      border: `1px solid ${isFallback ? "#272727" : "#272727"}`,
      opacity: isFallback ? 0.55 : 1,
    }}>
      {/* Header row */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
        style={{ background: "#131313" }}
      >
        <span className="text-base font-black" style={{ color: isFallback ? "#4b5563" : "white" }}>{summary.ticker}</span>
        {isFallback ? (
          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#282828", color: "#6e6e6e", border: "1px solid #2e2e2e" }}>
            AI 생성 실패
          </span>
        ) : (
          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ ...rec }}>
            {summary.recommendation}
          </span>
        )}
        <span className="text-[12px] text-[#6b7280]">AI Analysis</span>

        {/* Score chips */}
        <div className="flex items-center gap-2 ml-auto">
          {[
            { label: "Composite", val: summary.composite_score },
            { label: "RS", val: summary.rs_score },
            { label: "Analyst", val: summary.analyst_score },
          ].map(({ label, val }) => val != null && (
            <div key={label} className="rounded px-2 py-1 text-center" style={{ background: "#222222", border: "1px solid #2e2e2e" }}>
              <p className="text-[12px] text-[#6b7280]">{label}</p>
              <p className="text-[13px] font-bold text-white">{typeof val === "number" ? Math.round(val) : val}</p>
            </div>
          ))}
          {/* Confidence */}
          <div className="rounded px-2 py-1 text-center" style={{ background: "#222222", border: "1px solid #2e2e2e" }}>
            <p className="text-[12px] text-[#6b7280]">Confidence</p>
            <p className="text-[13px] font-bold" style={{ color: isFallback ? "#4b5563" : "#39ff8f" }}>{conf}%</p>
          </div>
          <span className="text-[#6b7280] text-[13px] ml-1">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* Expanded content */}
      {open && (
        <div className="px-4 pb-4 pt-3 space-y-3">
          {isFallback ? (
            <p className="text-[12px]" style={{ color: "#6e6e6e" }}>
              API 한도 초과 또는 응답 오류로 AI 요약을 생성하지 못했습니다.
              분석을 다시 실행하면 생성될 수 있습니다.
            </p>
          ) : (
            <>
              <p className="text-[13px] leading-relaxed" style={{ color: "#c0c0c0" }}>{summary.thesis}</p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[12px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "#39ff8f" }}>상승 촉매</p>
                  <ul className="space-y-1">
                    {(summary.catalysts ?? []).map((c: string, i: number) => (
                      <li key={i} className="flex gap-1.5 text-[12px]" style={{ color: "#a8a8a8" }}>
                        <span style={{ color: "#39ff8f" }}>▲</span>{c}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-[12px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "#ef4444" }}>하락 리스크</p>
                  <ul className="space-y-1">
                    {(summary.bear_cases ?? []).map((b: string, i: number) => (
                      <li key={i} className="flex gap-1.5 text-[12px]" style={{ color: "#a8a8a8" }}>
                        <span style={{ color: "#ef4444" }}>▼</span>{b}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Confidence bar */}
              <div>
                <div className="flex justify-between text-[12px] text-[#6b7280] mb-1">
                  <span>AI Confidence</span><span>{conf}%</span>
                </div>
                <div className="h-1 rounded-full" style={{ background: "#282828" }}>
                  <div className="h-1 rounded-full" style={{ width: `${conf}%`, background: "#39ff8f" }} />
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function AIPage() {
  const { market } = useMarket();
  const [summaries, setSummaries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setSummaries([]);
    const url = market === "KR" ? "/api/data/kr/ai-summaries" : "/api/data/ai-summaries";
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data?.summaries)) setSummaries(data.summaries);
        else if (data?.ticker) setSummaries([data]);
        else setSummaries([]);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [market]);

  const isKR = market === "KR";
  const okCount   = summaries.filter((s) => !s._fallback && s.confidence > 0).length;
  const failCount = summaries.filter((s) => s._fallback || s.confidence === 0).length;

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
            <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{isKR ? "KOSPI" : "S&P 500"}
          </span>
          <h1 className="text-base font-bold text-white">AI 분석 리포트</h1>
          <InfoTooltip content="Gemini 2.5 Flash가 각 선별 종목의 투자 thesis, 성장 촉매(catalysts), 리스크 요인(bear cases)을 한국어로 요약한 리포트입니다." />
          {summaries.length > 0 && (
            <div className="ml-auto flex items-center gap-2">
              <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
                ✓ {okCount}건 성공
              </span>
              {failCount > 0 && (
                <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#4b556318", color: "#6e6e6e", border: "1px solid #33333333" }}>
                  ✗ {failCount}건 실패
                </span>
              )}
            </div>
          )}
        </div>
        <p className="text-[12px] text-[#6b7280]">
          Gemini 2.5 Flash 생성 — 투자 판단의 참고 자료로만 활용하세요.
          {isKR && " · run_kr_analysis.py 실행 시 BUY 종목 대상 자동 생성"}
        </p>
      </div>

      {loading && <p className="text-sm text-[#6b7280]">로딩 중…</p>}
      {!loading && summaries.length === 0 && (
        <div className="bg-card rounded-xl p-3">
          <p className="text-sm font-semibold text-white mb-1">AI 요약 데이터 없음</p>
          <p className="text-[12px] mb-2" style={{ color: "var(--text-muted)" }}>
            {isKR
              ? "python scripts/run_kr_analysis.py 실행 후 BUY 종목에 대한 AI 분석이 생성됩니다."
              : "alpharun 실행 후 자동으로 생성됩니다."}
          </p>
          <code className="block text-[12px] rounded-lg px-3 py-2" style={{ background: "var(--bg-inset)", color: "#39ff8f" }}>
            {isKR ? "python scripts/run_kr_analysis.py" : "alpharun"}
          </code>
        </div>
      )}

      <div className="space-y-2">
        {summaries.map((s: any, i: number) => (
          <AISummaryCard key={s.ticker ?? i} summary={s} idx={i} />
        ))}
      </div>
    </div>
  );
}
