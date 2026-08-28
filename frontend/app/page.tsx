"use client";

import { useEffect, useState } from "react";
import InfoTooltip from "@/src/components/InfoTooltip";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";

export default function HomePage() {
  const { market } = useMarket();
  const [candidateCount, setCandidateCount] = useState<number | null>(null);

  useEffect(() => {
    setCandidateCount(null);
    fetch(`/api/watchlist/candidates?market=${market}`)
      .then(r => r.json())
      .then(d => setCandidateCount((d?.candidates ?? []).length))
      .catch(() => setCandidateCount(0));
  }, [market]);

  const isKR = market === "KR";
  const indexName = isKR ? "KOSPI" : "S&P 500";

  if (candidateCount === null) return (
    <div className="space-y-3">
      <div className="h-32 rounded-xl animate-pulse" style={{ background: "#111009" }} />
    </div>
  );

  return (
    <div className="space-y-3">
      {/* Title */}
      <div className="flex items-center gap-3">
        <span className="text-[13px] font-bold px-2 py-0.5 rounded" style={{ background: "#262112", color: "#726b58" }}>
          <FlagIcon market={isKR ? "KR" : "US"} size={14} />{" "}{indexName}
        </span>
        <h1 className="text-xl font-bold text-white">
          {isKR ? "한국 주식 마켓 인텔리전스" : "미국 주식 마켓 인텔리전스"}
        </h1>
        <span className="rounded px-2 py-0.5 text-[13px] font-bold" style={{ background: "#ffb02022", color: "#ffb020", border: "1px solid #ffb02044" }}>
          LIVE
        </span>
      </div>

      {/* 워치리스트 후보 — 순위 없는 리스트업 (Primary) */}
      <a href="/watchlist" className="card-primary block" style={{ background: "var(--bg-raised)" }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1.5">
              <p className="stat-label" style={{ fontSize: 13 }}>이번 주 워치리스트 후보</p>
              <InfoTooltip content="재무 건전성 필터(Piotroski 등)를 통과한 종목을 순위 없이 리스트업합니다. 매수 신호가 아닙니다." />
            </div>
            <p className="text-5xl font-black mt-1" style={{ color: "#ffb020" }}>
              {candidateCount}
              <span className="text-lg font-normal ml-2" style={{ color: "var(--text-faint)" }}>개</span>
            </p>
            <p className="text-[13px] mt-1" style={{ color: "var(--text-secondary)" }}>
              재무 필터 통과, 순위 없음 — 탭해서 직접 검토
            </p>
          </div>
          <span className="text-[13px] shrink-0" style={{ color: "var(--text-muted)" }}>확인하기 →</span>
        </div>
      </a>

      {candidateCount === 0 && (
        <div className="bg-card rounded-lg p-3 text-center text-base" style={{ color: "#726b58" }}>
          이번 주 통과 후보가 없습니다. GitHub → Actions → Weekly Watchlist Screen 실행 여부를 확인하세요.
        </div>
      )}

      {/* 이동 링크 */}
      <div className="grid grid-cols-2 gap-2">
        <a href="/briefing" className="bg-card rounded-lg p-3 block">
          <p className="stat-label mb-1" style={{ fontSize: 13 }}>주간 브리핑</p>
          <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
            지난주 지수 흐름·워치리스트 변동·관심도 요약
          </p>
        </a>
        <a href="/sector" className="bg-card rounded-lg p-3 block">
          <p className="stat-label mb-1" style={{ fontSize: 13 }}>섹터 분석</p>
          <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
            {indexName} 섹터별 상대강도
          </p>
        </a>
      </div>
    </div>
  );
}
