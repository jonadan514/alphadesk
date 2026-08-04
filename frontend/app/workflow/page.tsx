"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMarket } from "@/src/contexts/MarketContext";
import FlagIcon from "@/src/components/FlagIcon";
import StatusBadge from "@/src/components/StatusBadge";
import InfoTooltip from "@/src/components/InfoTooltip";
import { SECTOR_TO_ETF } from "@/src/lib/constants";

type Signal = "GO" | "CAUTION" | "STOP" | "LOADING";

interface StepStatus {
  signal: Signal;
  title: string;
  summary: string;
  detail: string;
  action: string;
  proceed: boolean;
}

const SIG_COLOR: Record<Signal, string> = {
  GO: "#4ade80", CAUTION: "#facc15", STOP: "#f87171", LOADING: "#423e33",
};
const SIG_BG: Record<Signal, string> = {
  GO: "#4ade8018", CAUTION: "#facc1518", STOP: "#f8717118", LOADING: "#111009",
};
const SIG_ICON: Record<Signal, string> = {
  GO: "✓", CAUTION: "!", STOP: "✕", LOADING: "·",
};
const SIG_LABEL: Record<Signal, string> = {
  GO: "정상", CAUTION: "주의", STOP: "위험", LOADING: "로딩",
};

const REGIME_SIZE: Record<string, { pct: string; desc: string }> = {
  risk_on:  { pct: "70~80%", desc: "공격적 매수, 성장주 중심" },
  neutral:  { pct: "50~60%", desc: "표준 비중, 균형 포트폴리오" },
  risk_off: { pct: "30~40%", desc: "방어주·배당주 중심" },
  crisis:   { pct: "10~20%", desc: "현금 최대화, 헤지 검토" },
};
const STOP_LOSS: Record<string, string> = {
  risk_on: "-10%", neutral: "-8%", risk_off: "-5%", crisis: "-3%",
};

const STEP_META = [
  { linkHref: "/",          linkLabel: "개요" },
  { linkHref: "/regime",    linkLabel: "시장 체제" },
  { linkHref: "/top-picks", linkLabel: "종목 분석" },
  { linkHref: "/top-picks", linkLabel: "종목 분석" },
  { linkHref: "/risk",      linkLabel: "리스크" },
  { linkHref: "/regime",    linkLabel: "시장 체제" },
];

function verdictSignal(v: string): Signal {
  if (v === "GO") return "GO";
  if (v === "CAUTION") return "CAUTION";
  if (v === "STOP") return "STOP";
  return "CAUTION";
}

// ── 상단 종합 판단 히어로 ────────────────────────────────────────────────────
function HeroVerdict({
  overall, actions, regimeName, cycleLabel, date,
}: {
  overall: Signal;
  actions: string[];
  regimeName: string;
  cycleLabel: string;
  date: string;
}) {
  const color = SIG_COLOR[overall];
  const bg    = SIG_BG[overall];

  const overallMsg: Record<Signal, string> = {
    GO:      "모든 신호 정상 — 신규 진입 가능",
    CAUTION: "일부 경계 신호 — 신중하게 접근",
    STOP:    "시장 불리 — 신규 진입 자제",
    LOADING: "",
  };

  return (
    <div className="rounded-xl p-5" style={{ background: bg, border: `1.5px solid ${color}44` }}>
      <div className="flex items-start gap-3">
        {/* 큰 신호 배지 */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-black"
            style={{ background: `${color}22`, border: `2px solid ${color}66`, color }}
          >
            {SIG_ICON[overall]}
          </div>
          <span className="text-[12px] font-bold uppercase tracking-widest" style={{ color }}>
            {overall}
          </span>
        </div>

        {/* 판단 + 할 일 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-base font-black text-white">{overallMsg[overall]}</p>
          </div>
          <p className="text-[12px] mb-2" style={{ color: "var(--text-muted)" }}>
            {date && `${date} · `}
            {regimeName && `체제 ${regimeName.replace("_", " ")} · `}
            {cycleLabel && `사이클 ${cycleLabel}`}
          </p>

          {/* 오늘 할 일 */}
          {actions.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color }}>
                오늘 할 일
              </p>
              {actions.map((a, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-[12px] font-black mt-0.5 shrink-0" style={{ color }}>
                    {i + 1}.
                  </span>
                  <p className="text-[12px] text-white leading-snug">{a}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 신호 그리드 카드 ────────────────────────────────────────────────────────
function SignalCard({
  step, status, isOpen, onClick, linkHref, linkLabel,
}: {
  step: number;
  status: StepStatus;
  isOpen: boolean;
  onClick: () => void;
  linkHref: string;
  linkLabel: string;
}) {
  const color = SIG_COLOR[status.signal];
  const bg    = SIG_BG[status.signal];

  return (
    <div
      className="rounded-xl overflow-hidden transition-all"
      style={{ border: `1px solid ${isOpen ? color + "55" : color + "22"}`, background: "#111009" }}
    >
      {/* 컴팩트 헤더 */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors"
        style={{ background: isOpen ? bg : "transparent" }}
        onClick={onClick}
      >
        <span
          className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[12px] font-black"
          style={{ background: color, color: "#0a0a08" }}
        >
          {SIG_ICON[status.signal]}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-bold" style={{ color: "var(--text-faint)" }}>
              STEP {step}
            </span>
            <span className="text-[12px] font-bold" style={{ color }}>
              {SIG_LABEL[status.signal]}
            </span>
          </div>
          <p className="text-[13px] font-semibold text-white truncate">{status.title}</p>
        </div>
        <span className="text-[12px] text-[#423e33]">{isOpen ? "▲" : "▼"}</span>
      </button>

      {/* 요약 한 줄 (항상 보임) */}
      {!isOpen && (
        <div className="px-4 pb-3">
          <p className="text-[12px] truncate" style={{ color: "var(--text-muted)" }}>
            {status.summary}
          </p>
        </div>
      )}

      {/* 상세 (열렸을 때) */}
      {isOpen && (
        <div className="px-4 pb-4 pt-2 space-y-3" style={{ borderTop: `1px solid ${color}22` }}>
          <p className="text-[12px] leading-relaxed" style={{ color: "#a39c88" }}>
            {status.summary}
          </p>
          <p className="text-[12px] leading-relaxed" style={{ color: "#a39c88" }}>
            {status.detail}
          </p>
          <div className="rounded-lg px-3 py-2" style={{ background: `${color}0d`, border: `1px solid ${color}33` }}>
            <p className="text-[12px] font-bold uppercase tracking-widest mb-0.5" style={{ color }}>권장 행동</p>
            <p className="text-[12px] font-semibold text-white">{status.action}</p>
          </div>
          <Link
            href={linkHref}
            className="text-[12px] font-semibold hover:underline underline-offset-2"
            style={{ color: "var(--text-muted)" }}
          >
            {linkLabel} 탭 자세히 보기 →
          </Link>
        </div>
      )}
    </div>
  );
}

// ── 매수 전 체크리스트 ────────────────────────────────────────────────────────
function PreTradeChecklist({
  steps, reports, sector, market, aiMap, regimeName,
}: {
  steps: StepStatus[];
  overall: Signal;
  reports: any[];
  sector: any;
  market: string;
  aiMap: Record<string, any>;
  regimeName: string;
}) {
  const [ticker,     setTicker]     = useState(() => {
    // 워치리스트 상세의 "매수 체크로 이동" CTA가 넘긴 ?symbol= 을 초기값으로
    if (typeof window !== "undefined") {
      return (new URLSearchParams(window.location.search).get("symbol") ?? "").toUpperCase();
    }
    return "";
  });
  const [stopPrice,  setStopPrice]  = useState("");
  const [shares,     setShares]     = useState("");
  const [totalCap,   setTotalCap]   = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("alphaDesk_totalCap") ?? "";
    return "";
  });
  const [riskPct,    setRiskPct]    = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("alphaDesk_riskPct") ?? "2";
    return "2";
  });
  const [winRate,    setWinRate]    = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("alphaDesk_winRate") ?? "";
    return "";
  });
  const [rrRatio,    setRrRatio]    = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("alphaDesk_rrRatio") ?? "";
    return "";
  });

  // 입력값을 localStorage에 저장
  useEffect(() => {
    if (typeof window !== "undefined") {
      if (totalCap) localStorage.setItem("alphaDesk_totalCap", totalCap);
      if (riskPct)  localStorage.setItem("alphaDesk_riskPct", riskPct);
      if (winRate)  localStorage.setItem("alphaDesk_winRate", winRate);
      if (rrRatio)  localStorage.setItem("alphaDesk_rrRatio", rrRatio);
    }
  }, [totalCap, riskPct, winRate, rrRatio]);

  // 실시간 원/달러 환율 — "총 투자 자금"은 항상 원화로 입력받고, 미국 종목이면
  // 이 환율로 내부에서 달러로 환산해 계산한다 (시장 전환 시 단위 혼동 방지).
  const [fxRate, setFxRate]   = useState<number | null>(null);
  const [fxError, setFxError] = useState(false);
  useEffect(() => {
    fetch("/api/fx/usdkrw")
      .then((r) => r.json())
      .then((d) => { if (typeof d.rate === "number") setFxRate(d.rate); else setFxError(true); })
      .catch(() => setFxError(true));
  }, []);

  // 전체 채점 결과 (top-20 밖 종목 포함) — 워치리스트 종목이 오늘 top-20에 없어도
  // 등급·액션으로 매수체크가 되도록 폴백 소스로 사용한다. (AI thesis는 top-20에만 있음)
  const [fullScores, setFullScores] = useState<any[]>([]);
  useEffect(() => {
    const url = market === "KR" ? "/api/data/kr/full-scores" : "/api/data/full-scores";
    fetch(url)
      .then((r) => r.json())
      .then((d) => setFullScores(Array.isArray(d?.scores) ? d.scores : []))
      .catch(() => {});
  }, [market]);

  const latestPicks: any[] = reports[0]?.picks ?? [];
  const tickerUp = ticker.trim().toUpperCase();
  const matchTicker = (p: any) =>
    (p.symbol ?? "").toUpperCase() === tickerUp || (p.name ?? "").includes(tickerUp);
  // 1순위: 오늘 top-20 리포트(AI thesis 포함). 없으면 전체 채점 폴백(등급·액션만).
  const pick = tickerUp ? (latestPicks.find(matchTicker) ?? fullScores.find(matchTicker) ?? null) : null;
  const pickFromReport = tickerUp ? latestPicks.some(matchTicker) : false; // top-20 리포트 출처 여부
  const pickFromFallback = !!pick && !pickFromReport;                       // 전체 채점 폴백 출처

  // 워치리스트 후보 자동 판정
  const [candidateSet, setCandidateSet] = useState<Set<string>>(new Set());
  useEffect(() => {
    fetch("/api/watchlist/candidates")
      .then((r) => r.json())
      .then((d) => setCandidateSet(new Set(
        ((d.candidates ?? []) as { market: string; symbol: string }[]).map((c) => `${c.market}:${c.symbol}`)
      )))
      .catch(() => {});
  }, []);

  // 내 워치리스트 — 티커 빠른 선택용
  // 다른 탭(워치리스트 페이지)에서 종목을 추가한 뒤 새로고침 없이 돌아올 때도
  // 최신 목록이 보이도록 마운트 시 + 탭 포커스 복귀 시 재조회한다.
  const [myWatchlist, setMyWatchlist] = useState<{ market: string; symbol: string; name: string | null }[]>([]);
  useEffect(() => {
    const load = () => {
      fetch("/api/watchlist/my")
        .then((r) => r.json())
        .then((rows) => setMyWatchlist(Array.isArray(rows) ? rows : []))
        .catch(() => {});
    };
    load();
    window.addEventListener("focus", load);
    document.addEventListener("visibilitychange", load);
    return () => {
      window.removeEventListener("focus", load);
      document.removeEventListener("visibilitychange", load);
    };
  }, []);
  const myWatchlistForMarket = myWatchlist.filter((w) => w.market === market);
  const watchSymbol = (pick?.symbol ?? tickerUp).toUpperCase();
  const watchOk = !!tickerUp && candidateSet.has(`${market}:${watchSymbol}`);

  // 수동 확인 항목 (종목 바뀌면 다시 체크하도록 초기화)
  const [manualOk, setManualOk] = useState<Record<string, boolean>>({});
  useEffect(() => { setManualOk({}); }, [tickerUp]);

  const isKR    = market === "KR";
  const isBuy   = pick?.action === "BUY";
  const gradeOk = pick ? (pick.grade === "A" || pick.grade === "B") : false;
  const scoreOk = pick ? (pick.composite_score ?? 0) >= 60 : false;

  const leadingList: string[] = isKR
    ? (sector?.leading ?? []).map((l: any) => l.sector)
    : (sector?.leading ?? []).map((l: any) => l.ticker);
  const sectorOk = pick ? (isKR
    ? leadingList.includes(pick.sector ?? "")
    : leadingList.includes(SECTOR_TO_ETF[pick.sector ?? ""] ?? "")
  ) : false;

  // AI thesis: 해당 종목의 AI 데이터가 존재하면 자동 체크
  const aiData  = tickerUp ? (aiMap[tickerUp] ?? aiMap[pick?.name ?? ""] ?? null) : null;
  const aiOk    = !!aiData;

  // 손절가: 입력된 손절가가 현재가보다 낮으면 체크
  const curPrice   = isKR ? (pick?.cur_price ?? 0) : (pick?.current_price ?? 0);
  const stopNum    = parseFloat(stopPrice);
  const stopOk     = stopPrice !== "" && !isNaN(stopNum) && stopNum > 0 && (curPrice === 0 || stopNum < curPrice);

  // 매수 수량: 입력값이 1 이상의 정수이면 체크
  const sharesNum  = parseInt(shares, 10);
  const sharesOk   = shares !== "" && !isNaN(sharesNum) && sharesNum >= 1;

  // 권장 손절선 계산 (현재가 기준)
  const stopLossPct = STOP_LOSS[regimeName] ?? "-8%";
  const recStopNum  = curPrice > 0
    ? (curPrice * (1 + parseFloat(stopLossPct) / 100)).toFixed(isKR ? 0 : 2)
    : null;

  // 손절가 입력 시 손실금액 계산
  const stopLossAmt = stopOk && sharesOk && curPrice > 0
    ? ((stopNum - curPrice) * sharesNum)
    : null;

  // ── 포지션 사이징 역산 ────────────────────────────────────────────
  // "총 투자 자금"은 항상 원화(₩)로 입력받는다. 미국 종목이면 실시간 환율로
  // 내부에서 달러로 환산해 계산한다 — 시장 전환 시 같은 숫자가 원↔달러로
  // 잘못 재해석되던 문제를 근본적으로 없앤다.
  const totalCapWon  = parseFloat(totalCap.replace(/,/g, ""));
  const riskPctNum   = parseFloat(riskPct);
  const entryPrice   = curPrice > 0 ? curPrice : parseFloat(stopPrice) / (1 - 0.08); // fallback
  const stopNum2     = parseFloat(stopPrice);
  const capOk        = totalCap !== "" && !isNaN(totalCapWon) && totalCapWon > 0;
  const fxReady      = isKR || (fxRate !== null);
  const totalCapNum  = capOk ? (isKR ? totalCapWon : (fxRate ? totalCapWon / fxRate : NaN)) : NaN;
  const riskOk2      = riskPct !== "" && !isNaN(riskPctNum) && riskPctNum > 0 && riskPctNum <= 20;
  const canCalc      = capOk && fxReady && riskOk2 && stopOk && entryPrice > 0 && stopNum2 > 0 && stopNum2 < entryPrice;

  const maxLossMoney   = capOk && fxReady && riskOk2 ? totalCapNum * (riskPctNum / 100) : null;
  const recShares      = canCalc && maxLossMoney ? Math.floor(maxLossMoney / (entryPrice - stopNum2)) : null;
  const recPositionAmt = recShares && entryPrice > 0 ? recShares * entryPrice : null;
  const recPositionPct = recPositionAmt && capOk && fxReady ? (recPositionAmt / totalCapNum) * 100 : null;
  const recLossAmt     = recShares && entryPrice > 0 ? recShares * (entryPrice - stopNum2) : null;
  // 원화 환산 표시용 (미국 종목일 때만 의미 있음)
  const recPositionWon = !isKR && recPositionAmt && fxRate ? recPositionAmt * fxRate : null;
  const recLossWon     = !isKR && recLossAmt && fxRate ? recLossAmt * fxRate : null;

  // ── 켈리 검증 (선택 입력) ────────────────────────────────────────
  const winNum  = parseFloat(winRate);
  const rrNum   = parseFloat(rrRatio);
  const kellyF  = !isNaN(winNum) && winNum > 0 && winNum < 100 && !isNaN(rrNum) && rrNum > 0
    ? winNum / 100 - (1 - winNum / 100) / rrNum
    : null;
  const kellyCapped = kellyF !== null && kellyF > 0.25;   // 25% 상한
  const kellyPct    = kellyF !== null ? Math.min(Math.max(kellyF, 0), 0.25) : null;
  const kellyShares = kellyPct !== null && kellyPct > 0 && capOk && fxReady && entryPrice > 0
    ? Math.floor((totalCapNum * kellyPct) / entryPrice)
    : null;

  // 손익비(R:R) 자동 계산 — 목표가·손절가가 있으면 추측 대신 계산으로 채운다.
  //   손익비 = (목표가 − 현재가) ÷ (현재가 − 손절가)
  const targetRaw = parseFloat(pick?.target_price ?? aiData?.target_price ?? "");
  const targetPrice = !isNaN(targetRaw) && targetRaw > 0 ? targetRaw : null;
  const autoRR = (targetPrice && curPrice > 0 && stopOk && stopNum < curPrice && targetPrice > curPrice)
    ? (targetPrice - curPrice) / (curPrice - stopNum)
    : null;

  // ── 각 조건 상태 산출 (2026-07: pass boolean → PASS/WARN/FAIL/PENDING) ──
  // 목적: "아직 미입력·미선택(PENDING)"과 "실제 미충족(FAIL)"을 구분하고,
  // STOP 시장 게이트/체제/리스크가 회색으로 숨던 문제를 실제 경고색으로 드러낸다.
  // 원칙: PASS 판정 임계값은 기존과 100% 동일. 비통과 항목의 표현만 세분화한다.
  //   gate    : GO만 통과(기존 gateOk = ===GO)
  //   regime/risk : STOP만 미통과(기존 = !==STOP, 즉 CAUTION은 통과 유지)
  //   종목 조건 : pick/tickerUp 없으면 PENDING(기존엔 회색, 통과 카운트 동일)
  type CkStatus = "PASS" | "WARN" | "FAIL" | "PENDING";
  // !STOP 통과형(체제·리스크): STOP=FAIL, 로딩=PENDING, 그 외(GO·CAUTION)=PASS
  const notStop = (sig: Signal | undefined): CkStatus =>
    sig === undefined || sig === "LOADING" ? "PENDING" : sig === "STOP" ? "FAIL" : "PASS";
  const gateSig = steps[0]?.signal;
  const stGate: CkStatus = gateSig === "GO" ? "PASS" : gateSig === "STOP" ? "FAIL" : gateSig === "CAUTION" ? "WARN" : "PENDING";
  const stRegime = notStop(steps[1]?.signal);
  const stRisk   = notStop(steps[4]?.signal);
  const stWatch:  CkStatus = !tickerUp ? "PENDING" : watchOk  ? "PASS" : "WARN";
  const stBuy:    CkStatus = !pick     ? "PENDING" : isBuy    ? "PASS" : "FAIL";
  const stGrade:  CkStatus = !pick     ? "PENDING" : gradeOk  ? "PASS" : "FAIL";
  const stScore:  CkStatus = !pick     ? "PENDING" : scoreOk  ? "PASS" : "FAIL";
  const stAi:     CkStatus = !tickerUp ? "PENDING" : aiOk     ? "PASS" : "WARN";
  const stWorkbook: CkStatus = manualOk.workbook ? "PASS" : "PENDING";
  const stFunds:    CkStatus = manualOk.funds    ? "PASS" : "PENDING";
  const stStop: CkStatus = stopPrice === "" ? "PENDING" : stopOk   ? "PASS" : "WARN";
  const stSize: CkStatus = shares    === "" ? "PENDING" : sharesOk ? "PASS" : "WARN";

  interface CkItem { id: string; label: string; status: CkStatus; manual?: boolean; tip: string }
  const CK_GROUPS: { key: string; label: string; verb: string; items: CkItem[] }[] = [
    {
      key: "auto", label: "자동 검증", verb: "통과",
      items: [
        { id: "gate",      label: "시장 게이트 GO",                          status: stGate,   tip: "시장 진입 신호가 GO여야 합니다." },
        { id: "regime",    label: "체제 Risk-on / Neutral",                  status: stRegime, tip: "Risk-off·Crisis 체제에서는 신규 매수를 자제하세요." },
        { id: "watchlist", label: `${tickerUp || "종목"} 워치리스트 후보 포함`, status: stWatch,
          tip: watchOk
            ? "적합 점수 상위 50 후보에 포함 — 재무 함정 필터 자동 통과"
            : "워치리스트 후보에 없음 — 함정 필터 미통과이거나 적합 점수 상위 50 밖입니다. 워치리스트 탭에서 확인하세요." },
        { id: "risk",      label: "리스크 수준 허용 범위",                     status: stRisk,   tip: "VaR·MDD 경고 없을 때 진입하세요." },
        { id: "buy",       label: `${tickerUp || "종목"} BUY 액션 확인`,     status: stBuy,    tip: "스크리닝 BUY 액션 종목만 선택하세요." },
        { id: "grade",     label: `${tickerUp || "종목"} Grade A·B 확인`,   status: stGrade,  tip: "C등급 이하는 진입 자제를 권장합니다." },
        { id: "score",     label: `${tickerUp || "종목"} 점수 ≥ 60`,        status: stScore,  tip: `현재 점수: ${pick?.composite_score?.toFixed(1) ?? "—"}` },
        { id: "ai",        label: "AI 분석 thesis 확인",                     status: stAi,     tip: aiOk ? `${tickerUp} AI 분석 데이터 있음 — 아래에서 확인하세요.` : "종목 분석 탭에서 해당 종목 클릭 후 투자 근거와 리스크 요인을 확인하세요." },
      ],
    },
    {
      key: "manual", label: "사용자 판단", verb: "완료",
      items: [
        { id: "workbook",  label: "정성 검증 완료 — 클릭해서 체크", status: stWorkbook, manual: true, tip: "워치리스트 탭에서 종목을 클릭해 스토리·촉매 체크리스트를 점검했다면 이 항목을 클릭해 체크하세요." },
        { id: "funds",     label: "6개월 이상 묶여도 되는 여유 자금 — 클릭해서 체크", status: stFunds, manual: true, tip: "단기에 쓸 돈이면 매수하지 마세요. 확인했다면 클릭해 체크하세요." },
      ],
    },
    {
      key: "order", label: "주문 계획", verb: "입력",
      items: [
        { id: "stop", label: "손절가 설정",     status: stStop, tip: `권장 손절선: ${stopLossPct} (현재 체제 기준)` },
        { id: "size", label: "매수 수량 확정",   status: stSize, tip: "위 포지션 사이징 계산기로 자금·손실한도 입력 후 수량을 역산하세요." },
      ],
    },
  ];

  const allItems     = CK_GROUPS.flatMap((g) => g.items);
  const passCount    = allItems.filter((c) => c.status === "PASS").length;
  const totalCount   = allItems.length;
  const anyFail      = allItems.some((c) => c.status === "FAIL");
  const allPass      = passCount === totalCount;
  const overallColor = anyFail ? "#f87171" : allPass ? "#4ade80" : "#facc15";

  // 그룹 상태 칩 라벨 (그룹 성격에 맞게)
  const ckLabel = (groupKey: string, st: CkStatus): string => {
    if (groupKey === "manual") return st === "PASS" ? "완료" : "미체크";
    if (groupKey === "order")  return st === "PASS" ? "입력됨" : st === "WARN" ? "확인" : "미입력";
    return st === "PASS" ? "통과" : st === "FAIL" ? "미충족" : st === "WARN" ? "확인" : "대기";
  };
  const CK_ICON: Record<CkStatus, string> = { PASS: "✓", WARN: "!", FAIL: "✕", PENDING: "○" };
  const CK_COLOR: Record<CkStatus, string> = { PASS: "#4ade80", WARN: "#facc15", FAIL: "#f87171", PENDING: "#8b8271" };

  // ── ⓑ 최종 매수 가능 여부 한 문장 종합 ──────────────────────────
  // "무엇이 막고, 무엇을 하면 되는지"를 상태들로부터 합성한다.
  // 차단 조건: 시장/종목 FAIL, 주문(손절가·수량) 미완, 사용자 판단 미완.
  // 비차단(참고): 워치리스트 후보 밖·AI 상세 없음(WARN).
  const buildVerdict = (): { tone: CkStatus; headline: string; sub: string } => {
    if (!tickerUp) return { tone: "PENDING", headline: "종목을 선택하면 시장·종목 조건을 자동 판정합니다.", sub: "" };

    const marketFail = ([["게이트", stGate], ["체제", stRegime], ["리스크", stRisk]] as const)
      .filter(([, s]) => s === "FAIL").map(([n]) => n);
    const stockFail = ([["BUY 액션", stBuy], ["등급 A·B", stGrade], ["점수 60↑", stScore]] as const)
      .filter(([, s]) => s === "FAIL").map(([n]) => n);

    // 참고성 경고 (매수를 막지는 않음)
    const advisories: string[] = [];
    if (stWatch === "WARN") advisories.push("워치리스트 후보 밖");
    if (stAi === "WARN")    advisories.push("AI 상세 분석 없음");
    const advisorySub = advisories.length ? `참고: ${advisories.join(" · ")}` : "";

    if (marketFail.length) {
      return { tone: "FAIL", headline: `지금 시장이 신규 진입에 부적합 (${marketFail.join("·")} 미충족) — 매수 보류.`,
        sub: "시장 신호가 회복된 뒤 다시 검토하세요." };
    }
    if (stockFail.length) {
      return { tone: "FAIL", headline: `${tickerUp}은(는) 종목 조건 미달 (Grade ${pick?.grade ?? "-"} · ${pick?.action ?? "-"}) — 매수 보류.`,
        sub: "BUY·A/B 등급 종목을 고르거나, 근거가 확실하면 본인 판단으로 진행하세요." };
    }

    // 차단 FAIL 없음 → 남은 필수 항목(사용자 판단·주문 계획) 점검
    const manualDone = stWorkbook === "PASS" && stFunds === "PASS";
    const orderReady = stStop === "PASS" && stSize === "PASS";
    const needs: string[] = [];
    if (!manualDone) needs.push("정성 검증·자금 확인 체크");
    if (!orderReady) needs.push(
      (stStop === "WARN" || stSize === "WARN") ? "손절가·수량 재확인" : "손절가·수량 입력"
    );

    if (needs.length === 0) {
      return { tone: "PASS", headline: `✓ 필수 조건 모두 충족 — ${tickerUp} 매수 실행 가능.`, sub: advisorySub };
    }
    return { tone: "WARN", headline: `필수 조건은 통과 — ${needs.join(" + ")} 후 매수 가능.`, sub: advisorySub };
  };
  const verdict = buildVerdict();
  const verdictColor = CK_COLOR[verdict.tone];

  // 매수체크 값 → 포트폴리오 매수 폼 프리필 딥링크 (실제 체결가는 사용자가 확인·저장)
  const recordNote = `매수체크${pick ? ` · Grade ${pick.grade} ${pick.action}` : ""}${stopOk ? ` · 손절 ${stopPrice}` : ""}`;
  const recordHref = `/portfolio?market=${market}&symbol=${encodeURIComponent(tickerUp)}`
    + (pick?.name ? `&name=${encodeURIComponent(pick.name)}` : "")
    + (sharesOk ? `&shares=${sharesNum}` : "")
    + (curPrice > 0 ? `&price=${curPrice}` : "")
    + `&note=${encodeURIComponent(recordNote)}`;

  const inputCls = "rounded-lg px-3 py-1.5 text-sm font-mono text-white outline-none w-full";
  const inputStyle = { background: "var(--bg-inset)", border: "1px solid var(--border)" };

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #262112", background: "#111009" }}>
      <div className="px-4 py-3 flex items-center gap-3" style={{ background: "#0e0d08", borderBottom: "1px solid #111009" }}>
        <p className="text-[12px] font-bold uppercase tracking-widest text-white">매수 전 체크리스트</p>
        <div className="flex-1" />
        <span className="text-[12px] font-bold px-2 py-0.5" style={{ color: overallColor, background: `${overallColor}22`, border: `1px solid ${overallColor}44` }}>
          {anyFail ? "미충족 있음" : allPass ? "전체 충족" : "진행 중"}
        </span>
      </div>

      {/* 입력 영역 */}
      <div className="px-4 pt-3 pb-3 space-y-2">
        {/* 종목 */}
        <div>
          {myWatchlistForMarket.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {myWatchlistForMarket.map((w) => {
                const active = tickerUp === w.symbol.toUpperCase();
                return (
                  <button
                    key={`${w.market}:${w.symbol}`}
                    onClick={() => { setTicker(w.symbol.toUpperCase()); setStopPrice(""); setShares(""); }}
                    className="text-[12px] px-2.5 py-1 rounded-lg font-semibold transition-colors"
                    style={{
                      background: active ? "#ffb02022" : "#111009",
                      color: active ? "#ffb020" : "#a39c88",
                      border: `1px solid ${active ? "#ffb02044" : "#262112"}`,
                    }}
                  >
                    {w.symbol}{w.name ? ` · ${w.name}` : ""}
                  </button>
                );
              })}
            </div>
          )}
          <input
            type="text"
            value={ticker}
            onChange={(e) => { setTicker(e.target.value.toUpperCase()); setStopPrice(""); setShares(""); }}
            placeholder={isKR ? "종목 코드 입력 (예: 005930)" : "Ticker 입력 (예: AAPL)"}
            className={inputCls}
            style={inputStyle}
          />
          {tickerUp && pick && (
            <p className="text-[12px] mt-1" style={{ color: "#4ade80" }}>
              ✓ {pick.symbol}{pick.name ? ` (${pick.name})` : ""} — Grade {pick.grade} / {pick.composite_score?.toFixed(1)}점 / {pick.action}
              {curPrice > 0 && <span className="ml-2" style={{ color: "#a39c88" }}>현재가 {isKR ? `₩${Number(curPrice).toLocaleString()}` : `$${curPrice}`}</span>}
            </p>
          )}
          {tickerUp && pickFromFallback && (
            <p className="text-[12px] mt-0.5" style={{ color: "#726b58" }}>
              ⓘ 오늘 top-20 랭킹 밖 종목 — 등급·액션은 전체 채점 결과 기준이며, AI 상세 분석은 top-20에만 제공돼요.
            </p>
          )}
          {tickerUp && !pick && (
            <p className="text-[12px] mt-1" style={{ color: "#726b58" }}>
              전체 채점 결과에서 찾을 수 없습니다 (상장폐지·신규상장·데이터 누락 등). 손절가·수량은 직접 입력해 체크할 수 있습니다.
            </p>
          )}
          {/* 선행 섹터 여부 — 판정 항목이 아닌 참고 정보 (미해당이어도 매수 진행 가능) */}
          {tickerUp && pick && leadingList.length > 0 && (
            <p className="text-[12px] mt-1" style={{ color: sectorOk ? "#4ade80" : "#726b58" }}>
              {sectorOk
                ? `✓ 선행 섹터(${leadingList.join(", ")}) 소속 — 지금 시장이 선호하는 업종`
                : `ⓘ 참고: 지금 선행 섹터는 ${leadingList.join(", ")} — ${pick.sector ?? "이 종목"}은 해당 없음 (매수를 막지는 않음)`}
            </p>
          )}
        </div>

        {/* 포지션 사이징 계산기 */}
        <div className="rounded-lg p-3 space-y-2" style={{ background: "#0e0d08", border: "1px solid #262112" }}>
          <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#facc15" }}>
            포지션 사이징 — 손실 한도 기반 수량 역산
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-[12px] text-[#726b58] mb-1">총 투자 자금 (₩)</p>
              <input
                type="number"
                value={totalCap}
                onChange={(e) => setTotalCap(e.target.value)}
                placeholder="예: 10000000"
                className={inputCls}
                style={{ ...inputStyle, borderColor: capOk ? "#facc1566" : "var(--border)" }}
              />
              {capOk && isKR && <p className="text-[12px] mt-0.5" style={{ color: "#726b58" }}>
                ₩{totalCapWon.toLocaleString()}
              </p>}
              {capOk && !isKR && (
                fxRate ? (
                  <p className="text-[12px] mt-0.5" style={{ color: "#726b58" }}>
                    ≈ ${totalCapNum.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    <span style={{ color: "#423e33" }}> (환율 {fxRate.toFixed(1)}원 기준, 실시간)</span>
                  </p>
                ) : fxError ? (
                  <p className="text-[12px] mt-0.5" style={{ color: "#f87171" }}>환율을 불러오지 못했습니다 — 새로고침 해보세요.</p>
                ) : (
                  <p className="text-[12px] mt-0.5" style={{ color: "#726b58" }}>환율 불러오는 중…</p>
                )
              )}
            </div>
            <div>
              <p className="text-[12px] text-[#726b58] mb-1">종목당 허용 손실 (%)</p>
              <input
                type="number"
                value={riskPct}
                onChange={(e) => setRiskPct(e.target.value)}
                placeholder="예: 2"
                min="0.1" max="20" step="0.5"
                className={inputCls}
                style={{ ...inputStyle, borderColor: riskOk2 ? "#facc1566" : "var(--border)" }}
              />
              {capOk && riskOk2 && maxLossMoney !== null && (
                <p className="text-[12px] mt-0.5" style={{ color: "#facc15" }}>
                  최대 손실 {isKR ? `₩${Math.round(maxLossMoney).toLocaleString()}` : `$${maxLossMoney.toFixed(0)}`}
                </p>
              )}
            </div>
          </div>

          {/* 역산 결과 */}
          {canCalc && recShares !== null && recShares > 0 ? (
            <div className="rounded-lg p-2.5 space-y-1.5" style={{ background: "#facc1508", border: "1px solid #facc1522" }}>
              <p className="text-[12px] font-bold" style={{ color: "#facc15" }}>계산 결과</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-[12px]" style={{ color: "#726b58" }}>권장 수량</p>
                  <p className="text-sm font-black text-white">{recShares}주</p>
                </div>
                <div>
                  <p className="text-[12px]" style={{ color: "#726b58" }}>포지션 크기</p>
                  <p className="text-sm font-black text-white">
                    {isKR ? `₩${Math.round(recPositionAmt ?? 0).toLocaleString()}` : `$${(recPositionAmt ?? 0).toFixed(0)}`}
                  </p>
                  {recPositionWon !== null && (
                    <p className="text-[12px]" style={{ color: "#726b58" }}>≈ ₩{Math.round(recPositionWon).toLocaleString()}</p>
                  )}
                  {recPositionPct !== null && (
                    <p className="text-[12px]" style={{ color: recPositionPct > 30 ? "#f87171" : "#726b58" }}>
                      자금의 {recPositionPct.toFixed(1)}%
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-[12px]" style={{ color: "#726b58" }}>손절 시 손실</p>
                  <p className="text-sm font-black" style={{ color: "#f87171" }}>
                    {isKR ? `₩${Math.round(recLossAmt ?? 0).toLocaleString()}` : `$${(recLossAmt ?? 0).toFixed(0)}`}
                  </p>
                  {recLossWon !== null && (
                    <p className="text-[12px]" style={{ color: "#f87171" }}>≈ ₩{Math.round(recLossWon).toLocaleString()}</p>
                  )}
                  <p className="text-[12px]" style={{ color: "#f87171" }}>(-{riskPctNum}%)</p>
                </div>
              </div>
              <button
                onClick={() => setShares(String(recShares))}
                className="w-full text-[12px] font-bold py-1 rounded-lg transition-all"
                style={{ background: "#facc1518", color: "#facc15", border: "1px solid #facc1533" }}
              >
                이 수량으로 적용 ({recShares}주)
              </button>
            </div>
          ) : capOk && riskOk2 && !fxReady ? (
            <p className="text-[12px]" style={{ color: "#726b58" }}>
              환율을 불러오는 중입니다 — 잠시 후 다시 확인하세요.
            </p>
          ) : capOk && riskOk2 ? (
            <p className="text-[12px]" style={{ color: "#726b58" }}>
              종목 입력 후 손절가를 설정하면 권장 수량이 계산됩니다.
            </p>
          ) : (
            <p className="text-[12px]" style={{ color: "#726b58" }}>
              총 투자 자금과 허용 손실 %를 입력하면 적정 수량을 자동 계산합니다.
            </p>
          )}

          {/* 켈리 검증 (선택) */}
          <div className="pt-2" style={{ borderTop: "1px solid #262112" }}>
            <p className="text-[12px] mb-1.5 flex items-center gap-1.5" style={{ color: "#726b58" }}>
              <span>켈리 검증 <span style={{ color: "#423e33" }}>(선택)</span> — 이 베팅이 수학적으로 우위가 있는지 확인</span>
              <InfoTooltip content={
                <div className="space-y-1.5">
                  <p><b style={{ color: "#e6e8eb" }}>켈리 공식</b>은 &quot;이길 확률 대비 손익비가 좋은 베팅인지, 그렇다면 자금의 몇 %가 최적인지&quot;를 알려줘요.</p>
                  <p><b style={{ color: "#e6e8eb" }}>승률(%)</b>: 이 매매에서 이길 확률. 40~60처럼 퍼센트로 입력 (55 = 55%). 자신의 과거 승률이나 보수적 추정치를 쓰세요.</p>
                  <p><b style={{ color: "#e6e8eb" }}>손익비(R:R)</b>: 맞았을 때 이익 ÷ 틀렸을 때 손실. <b style={{ color: "#e6e8eb" }}>추측이 아니라 계산돼요</b> — (목표가 − 현재가) ÷ (현재가 − 손절가). 예: 현재가 $100, 손절 $92, 목표 $116이면 16÷8 = 2.0.</p>
                  <p>공식: 켈리 = 승률 − (1−승률) ÷ 손익비. <span style={{ color: "#f87171" }}>음수면</span> 기대손실(진입 재고), <span style={{ color: "#4ade80" }}>양수면</span> 그 %가 이론상 최적 비율 (실전은 보통 그 절반 &apos;하프 켈리&apos;).</p>
                </div>
              } />
            </p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                value={winRate}
                onChange={(e) => setWinRate(e.target.value)}
                placeholder="예상 승률 % (예: 55)"
                min="1" max="99" step="1"
                className={inputCls}
                style={inputStyle}
              />
              <input
                type="number"
                value={rrRatio}
                onChange={(e) => setRrRatio(e.target.value)}
                placeholder="손익비 R:R (예: 2)"
                min="0.1" step="0.1"
                className={inputCls}
                style={inputStyle}
              />
            </div>

            {/* 손익비 자동 계산 — 목표가·손절가 기반 */}
            {autoRR !== null ? (
              <p className="text-[12px] mt-1.5 flex items-center gap-1.5" style={{ color: "#6fb3b8" }}>
                <span>
                  목표가 {isKR ? `₩${Number(targetPrice).toLocaleString()}` : `$${targetPrice!.toFixed(2)}`} 기준 손익비 ≈ <b>{autoRR.toFixed(1)}</b>
                </span>
                <button
                  type="button"
                  onClick={() => setRrRatio(autoRR.toFixed(2))}
                  className="px-1.5 py-0.5 rounded"
                  style={{ color: "#6fb3b8", background: "#6fb3b812", border: "1px solid #6fb3b833" }}
                  title="계산된 손익비를 입력칸에 채웁니다"
                >
                  적용
                </button>
              </p>
            ) : targetPrice !== null && !stopOk ? (
              <p className="text-[12px] mt-1.5" style={{ color: "var(--text-faint)" }}>
                손절가를 입력하면 목표가({isKR ? `₩${Number(targetPrice).toLocaleString()}` : `$${targetPrice.toFixed(2)}`}) 기준 손익비가 자동 계산돼요.
              </p>
            ) : null}

            {kellyF !== null && (
              kellyF <= 0 ? (
                <p className="text-[12px] mt-1.5 font-bold" style={{ color: "#f87171" }}>
                  ⚠ 켈리 값 음수 ({(kellyF * 100).toFixed(1)}%) — 이 승률·손익비 조합은 기대손실입니다. 진입 자체를 재고하세요.
                </p>
              ) : (
                <p className="text-[12px] mt-1.5" style={{ color: "#6fb3b8" }}>
                  켈리 기준 자금의 {((kellyPct ?? 0) * 100).toFixed(1)}%{kellyCapped && " (상한 25% 적용)"}
                  {kellyShares !== null && ` ≈ ${kellyShares}주`} — 위 고정 비율 결과와 비교해 <span className="font-bold">작은 쪽</span>을 권장
                </p>
              )
            )}
          </div>
        </div>

        {/* 손절가 + 매수 수량 */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <p className="text-[12px] text-[#726b58] mb-1 uppercase tracking-widest flex items-center gap-1">
              <span>손절가 {isKR ? "(₩)" : "($)"}</span>
              {recStopNum && (
                <button
                  type="button"
                  onClick={() => setStopPrice(String(recStopNum))}
                  className="normal-case tracking-normal px-1.5 py-0.5 rounded"
                  style={{ color: "#facc15", background: "#facc1512", border: "1px solid #facc1533" }}
                  title="권장 손절가를 입력칸에 채웁니다"
                >
                  권장 {isKR ? `₩${Number(recStopNum).toLocaleString()}` : `$${recStopNum}`} 적용
                </button>
              )}
            </p>
            <input
              type="number"
              value={stopPrice}
              onChange={(e) => setStopPrice(e.target.value)}
              placeholder={recStopNum ?? (isKR ? "예: 48000" : "예: 138.50")}
              className={inputCls}
              style={{ ...inputStyle, borderColor: stopOk ? "#ffb02066" : "var(--border)" }}
            />
            {stopOk && stopLossAmt !== null && (
              <p className="text-[12px] mt-0.5" style={{ color: "#f87171" }}>
                손실 {isKR ? `₩${Math.abs(stopLossAmt).toLocaleString()}` : `$${Math.abs(stopLossAmt).toFixed(0)}`} ({sharesNum}주 기준)
              </p>
            )}
            <p className="text-[12px] mt-1.5 leading-relaxed" style={{ color: "#726b58" }}>
              <span style={{ color: "#facc15" }}>O'Neil 원칙</span> 매수가 대비 -7~8% 하락 시 감정 없이 즉시 손절
            </p>
          </div>
          <div>
            <p className="text-[12px] text-[#726b58] mb-1 uppercase tracking-widest">매수 수량 (주)</p>
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder="예: 10"
              className={inputCls}
              style={{ ...inputStyle, borderColor: sharesOk ? "#ffb02066" : "var(--border)" }}
            />
            {sharesOk && curPrice > 0 && (
              <p className="text-[12px] mt-0.5" style={{ color: "#a39c88" }}>
                총 {isKR ? `₩${(curPrice * sharesNum).toLocaleString()}` : `$${(curPrice * sharesNum).toFixed(0)}`}
              </p>
            )}
          </div>
        </div>

        {/* AI thesis 미니 표시 */}
        {aiOk && aiData.thesis && (
          <div className="rounded-lg px-3 py-2 text-[12px] leading-relaxed" style={{ background: "#ffb02008", border: "1px solid #ffb02022", color: "#a39c88" }}>
            <span className="font-bold" style={{ color: "#ffb020" }}>AI Thesis </span>{aiData.thesis}
          </div>
        )}
      </div>

      <div className="px-4 pb-4 pt-2 space-y-3" style={{ borderTop: "1px solid #262112" }}>
        {!tickerUp && (
          <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
            종목을 선택하면 종목 조건(워치리스트·BUY·등급·점수·AI)을 검증합니다. 그전까지는 &quot;대기&quot; 상태예요.
          </p>
        )}
        {CK_GROUPS.map((group) => {
          const gPass = group.items.filter((it) => it.status === "PASS").length;
          const gFull = gPass === group.items.length;
          return (
            <div key={group.key} className="space-y-1.5">
              {/* 그룹 헤더 + 그룹별 카운터 */}
              <div className="flex items-center gap-2">
                <p className="text-[11px] font-bold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>{group.label}</p>
                <span className="text-[11px] font-mono" style={{ color: gFull ? "#4ade80" : "var(--text-faint)" }}>
                  {gPass}/{group.items.length} {group.verb}
                </span>
              </div>
              {group.items.map((item) => {
                const st  = item.status;
                const col = CK_COLOR[st];
                const isManual = !!item.manual;
                return (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 px-3 py-2"
                    onClick={isManual ? () => setManualOk((m) => ({ ...m, [item.id]: !m[item.id] })) : undefined}
                    style={{
                      background: st === "PASS" ? "#4ade8008" : st === "FAIL" ? "#f8717108" : "transparent",
                      border: `1px solid ${st === "PASS" ? "#4ade8022" : st === "FAIL" ? "#f8717133" : isManual ? "#26211266" : "#111009"}`,
                      cursor: isManual ? "pointer" : "default",
                    }}
                  >
                    <div
                      className="w-4 h-4 flex items-center justify-center text-[12px] font-black shrink-0"
                      style={{ background: st === "PASS" ? "#4ade8033" : "#111009", border: `1px solid ${col}66`, color: col }}
                    >
                      {CK_ICON[st]}
                    </div>
                    <span className="flex-1 text-[12px]" style={{ color: st === "PENDING" ? "#726b58" : "#a39c88" }}>
                      {item.label}
                    </span>
                    <StatusBadge status={st} label={ckLabel(group.key, st)} />
                    <span className="text-[12px]" style={{ color: "#726b58" }} title={item.tip}>?</span>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* ⓑ 최종 매수 가능 여부 한 문장 종합 */}
      <div className="px-4 py-3" style={{ background: `${verdictColor}0d`, borderTop: `1px solid ${verdictColor}22` }}>
        <p className="text-[13px] font-bold" style={{ color: verdictColor }}>{verdict.headline}</p>
        {verdict.sub && (
          <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>{verdict.sub}</p>
        )}
      </div>

      {/* 포트폴리오 기록 — 매수체크 값으로 포트폴리오 매수 폼을 채워서 연다 */}
      {tickerUp && (
        <div className="px-4 pb-4">
          <Link
            href={recordHref}
            className="block w-full py-2.5 text-[13px] font-bold text-center"
            style={{ background: "#ffb02018", color: "#ffb020", border: "1px solid #ffb02033" }}
          >
            📥 이 내용으로 포트폴리오에 매수 기록 →
          </Link>
          <p className="text-[11px] mt-1 text-center" style={{ color: "var(--text-faint)" }}>
            종목·수량·현재가가 매수 폼에 채워져요. 실제 체결가를 확인·수정한 뒤 저장하세요.
          </p>
        </div>
      )}
    </div>
  );
}

// ── 메인 페이지 ─────────────────────────────────────────────────────────────
export default function WorkflowPage() {
  const { market, setMarket } = useMarket();
  // 워치리스트 CTA가 넘긴 ?market= 이 현재 시장과 다르면 맞춰준다 (마운트 1회)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const qm = new URLSearchParams(window.location.search).get("market");
    if ((qm === "US" || qm === "KR") && qm !== market) setMarket(qm);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [openStep, setOpenStep] = useState<number | null>(null);
  const [steps, setSteps]       = useState<StepStatus[]>(
    Array(6).fill({ signal: "LOADING" as Signal, title: "로딩 중…", summary: "", detail: "", action: "", proceed: false })
  );
  const [overall, setOverall]     = useState<Signal>("LOADING");
  const [actions, setActions]     = useState<string[]>([]);
  const [regimeName, setRegimeName] = useState("");
  const [cycleLabel, setCycleLabel] = useState("");
  const [reportDate, setReportDate] = useState("");
  const [reports, setReports]     = useState<any[]>([]);
  const [sectorData, setSectorData] = useState<any>(null);
  const [aiMap, setAiMap]           = useState<Record<string, any>>({});

  useEffect(() => {
    setSteps(Array(6).fill({ signal: "LOADING" as Signal, title: "로딩 중…", summary: "", detail: "", action: "", proceed: false }));
    setOverall("LOADING");

    if (market === "KR") {
      Promise.allSettled([
        fetch("/api/data/kr/market-gate").then((r) => r.json()),
        fetch("/api/data/kr/regime").then((r) => r.json()),
        fetch("/api/data/kr/reports?limit=1").then((r) => r.json()),
        fetch("/api/data/kr/sector").then((r) => r.json()),
        fetch("/api/data/kr/ai-summaries").then((r) => r.json()),
      ]).then(([gateRes, regimeRes, reportsRes, sectorRes, aiRes]) => {
        const gate   = gateRes.status    === "fulfilled" ? gateRes.value    : {};
        const regime = regimeRes.status  === "fulfilled" ? regimeRes.value  : {};
        const report = reportsRes.status === "fulfilled" ? (reportsRes.value[0] ?? {}) : {};
        const sector = sectorRes.status  === "fulfilled" ? (sectorRes.value ?? {}) : {};

        const gateSignal  = gate.gate ?? "CAUTION";
        const rName       = regime.regime ?? "neutral";
        const picks: any[]= report.picks ?? [];
        const buyPicks    = picks.filter((p: any) => p.action === "BUY");
        const watchPicks  = picks.filter((p: any) => p.action === "WATCH");
        const clabel      = sector.cycle_label ?? "";
        const leadingSectors: string[] = (sector.leading ?? []).map((l: any) => l.sector);
        const regSize     = REGIME_SIZE[rName] ?? { pct: "50%", desc: "표준 비중" };
        const stopLoss    = STOP_LOSS[rName] ?? "-8%";

        const s1sig = verdictSignal(gateSignal);
        const s1: StepStatus = {
          signal: s1sig,
          title: "시장 진입 여부 (KOSPI)",
          summary: `게이트 ${gateSignal} · 체제 ${rName.replace("_", " ")}`,
          detail: gate.reason ?? "KOSPI 시장 체제 기반 진입 신호입니다.",
          action: s1sig === "GO" ? "KOSPI 신규 진입 가능 — 다음 단계 확인" : s1sig === "CAUTION" ? "신규 진입 자제, 기존 포지션 유지" : "포지션 정리, 현금 보유",
          proceed: s1sig !== "STOP",
        };

        const s2sig: Signal = rName === "risk_on" ? "GO" : rName === "neutral" ? "GO" : rName === "risk_off" ? "CAUTION" : "STOP";
        const s2: StepStatus = {
          signal: s2sig,
          title: "체제 & 투자 비중",
          summary: `${rName.replace("_", " ")} · 권장 ${regSize.pct}${clabel ? ` · 사이클 ${clabel}` : ""}`,
          detail: `KOSPI 4개 센서(추세·변동성·모멘텀·브레드스) 가중합: ${regime.weighted_score?.toFixed(2) ?? "—"}.${clabel ? ` 현재 ${clabel} 구간.` : ""}`,
          action: `투자 비중 ${regSize.pct} — ${regSize.desc}`,
          proceed: s2sig !== "STOP",
        };

        const s3sig: Signal = buyPicks.length >= 3 ? "GO" : buyPicks.length >= 1 ? "CAUTION" : "STOP";
        const topBuy = buyPicks.slice(0, 5).map((p: any) => `${p.symbol}(${p.name ?? ""})`).join(", ");
        const s3: StepStatus = {
          signal: s3sig,
          title: "KOSPI 종목 선택",
          summary: `BUY ${buyPicks.length}개 · WATCH ${watchPicks.length}개${topBuy ? ` · ${topBuy}` : ""}`,
          detail: `4팩터 스크리닝(기술·펀더멘털·RS·거래량) BUY: ${buyPicks.length}개.${leadingSectors.length > 0 ? ` 선행 섹터: ${leadingSectors.join(", ")}` : ""}`,
          action: buyPicks.length >= 3 ? `상위 3~5종목 선택: ${buyPicks.slice(0, 3).map((p: any) => p.symbol).join(", ")}` : "조건 종목 부족 — 대기",
          proceed: s3sig !== "STOP",
        };

        const krAiList: any[] = aiRes.status === "fulfilled"
          ? (aiRes.value?.summaries ?? (Array.isArray(aiRes.value) ? aiRes.value : []))
          : [];
        const krBuySummaries = krAiList.filter((s: any) => s.recommendation === "BUY" || s.action === "BUY");
        const s4: StepStatus = {
          signal: krBuySummaries.length >= 2 ? "GO" : krAiList.length > 0 ? "CAUTION" : "CAUTION",
          title: "AI 검증",
          summary: krAiList.length > 0
            ? `AI BUY 추천 ${krBuySummaries.length}개 · 전체 ${krAiList.length}개`
            : "AI 분석 데이터 없음 — 직접 재무제표 확인 권장",
          detail: krAiList.length > 0
            ? `GPT-4o가 분석한 ${krAiList.length}개 종목 중 BUY 추천은 ${krBuySummaries.length}개입니다. thesis(투자 근거)가 납득되고, bear cases(하락 리스크)를 감수할 수 있는 종목만 최종 선정하세요.`
            : "AI 분석 데이터가 없습니다. 재분석 실행 후 재확인하거나 PER·PBR·ROE를 직접 확인하세요.",
          action: krAiList.length > 0 ? "thesis 납득 + bear case 감수 가능 종목만 최종 선정" : "종목 클릭 → 재무제표 직접 확인 후 최종 선정",
          proceed: true,
        };

        const s5sig: Signal = rName === "risk_off" || rName === "crisis" ? "CAUTION" : "GO";
        const s5: StepStatus = {
          signal: s5sig,
          title: "리스크 관리",
          summary: `손절선 ${stopLoss} · KOSPI 60일 변동성 ${regime.vol_60d?.toFixed(1) ?? "—"}%`,
          detail: `KOSPI 60일 실현변동성 ${regime.vol_60d?.toFixed(1) ?? "—"}%. 권장 손절선 ${stopLoss}.`,
          action: `진입 시 손절선 ${stopLoss} 주문 설정`,
          proceed: true,
        };

        const s6: StepStatus = {
          signal: "CAUTION",
          title: "타이밍 확인",
          summary: `KOSPI 20일 모멘텀 ${regime.mom_20d?.toFixed(2) ?? "—"}%`,
          detail: `KOSPI 20일 수익률: ${regime.mom_20d?.toFixed(2) ?? "—"}%. ${(regime.mom_20d ?? 0) > 0 ? "양의 모멘텀 — 진입 우호적." : "음의 모멘텀 — 신중하게 접근."}`,
          action: (regime.mom_20d ?? 0) > 0 ? "모멘텀 양호 — 분산 진입 가능" : "모멘텀 약세 — 분할 매수 권장",
          proceed: true,
        };

        const newSteps = [s1, s2, s3, s4, s5, s6];
        setSteps(newSteps);
        setRegimeName(rName);
        setCycleLabel(clabel);
        setReportDate(report.analysis_date ?? "");
        setReports(reportsRes.status === "fulfilled" ? reportsRes.value : []);
        setSectorData(sector);
        if (aiRes.status === "fulfilled") {
          const list: any[] = aiRes.value?.summaries ?? (Array.isArray(aiRes.value) ? aiRes.value : []);
          const m: Record<string, any> = {};
          list.forEach((s: any) => { if (s.ticker) m[s.ticker] = s; });
          setAiMap(m);
        }

        const stops = newSteps.filter((s) => s.signal === "STOP").length;
        const cauts = newSteps.filter((s) => s.signal === "CAUTION").length;
        const ov: Signal = stops > 0 ? "STOP" : cauts >= 2 ? "CAUTION" : "GO";
        setOverall(ov);

        const todayActions: string[] = [];
        if (ov === "GO") {
          todayActions.push(buyPicks.length > 0 ? `BUY ${buyPicks.length}개 중 3~5종목: ${topBuy}` : "스크리닝 조건 종목 부족 — 재분석 필요");
          todayActions.push(`투자 비중 ${regSize.pct}, 손절선 ${stopLoss}`);
          todayActions.push("직접 재무제표·뉴스 확인 후 최종 선정");
        } else if (ov === "CAUTION") {
          todayActions.push("신규 매수 자제, 기존 포지션 유지");
          todayActions.push(`손절선 ${stopLoss} 엄수`);
          todayActions.push("다음 분석 후 재검토");
        } else {
          todayActions.push("전체 포지션 정리 — 현금 보유");
          todayActions.push("KOSPI 안정 신호 확인 후 재진입");
          todayActions.push("신규 매수 금지");
        }
        setActions(todayActions);
      });
      return;
    }

    Promise.allSettled([
      fetch("/api/data/market-gate").then((r) => r.json()),
      fetch("/api/data/regime").then((r) => r.json()),
      fetch("/api/data/reports?limit=1").then((r) => r.json()),
      fetch("/api/data/ai-summaries").then((r) => r.json()),
      fetch("/api/data/risk").then((r) => r.json()),
      fetch("/api/data/index-prediction").then((r) => r.json()),
      fetch("/api/data/sector").then((r) => r.json()),
    ]).then(([gateRes, regimeRes, reportsRes, aiRes, riskRes, predRes, sectorRes]) => {
      const gate   = gateRes.status    === "fulfilled" ? gateRes.value    : {};
      const regime = regimeRes.status  === "fulfilled" ? regimeRes.value  : {};
      const report = reportsRes.status === "fulfilled" ? (reportsRes.value[0] ?? {}) : {};
      const ai     = aiRes.status      === "fulfilled" ? aiRes.value      : {};
      const risk   = riskRes.status    === "fulfilled" ? riskRes.value    : {};
      const pred   = predRes.status    === "fulfilled" ? predRes.value    : {};
      const sector = sectorRes.status  === "fulfilled" ? (sectorRes.value ?? {}) : {};

      const verdict    = report.verdict ?? gate.gate ?? "CAUTION";
      const rName      = regime.regime ?? "neutral";
      const picks: any[] = report.picks ?? [];
      const buyPicks   = picks.filter((p: any) => p.action === "BUY" && (p.grade === "A" || p.grade === "B"));
      const var95      = risk.var_95 ?? null;
      const mdd        = risk.mdd ?? null;
      const spy        = pred.spy ?? (pred.direction ? pred : null);
      const qqq        = pred.qqq ?? null;
      const summaries  = Array.isArray(ai.summaries) ? ai.summaries : [];
      const regSize    = REGIME_SIZE[rName] ?? { pct: "50%", desc: "표준 비중" };
      const stopLoss   = STOP_LOSS[rName] ?? "-8%";
      const spyDir     = spy?.direction;
      const spyPct     = spy?.probability ? Math.round(spy.probability * 100) : null;
      const clabel     = sector.cycle_label ?? "";

      const leadingEtfs: string[] = (sector.leading ?? []).map((l: any) => l.ticker);
      const alignedPicks = buyPicks.filter((p: any) => leadingEtfs.includes(SECTOR_TO_ETF[p.sector ?? ""] ?? ""));

      // 섹터 분산 추천 목록 구성
      // 1) 선행 섹터에서 최대 2종목
      const leadingSlots = alignedPicks.slice(0, 2);
      const usedSectors  = new Set(leadingSlots.map((p: any) => p.sector ?? ""));
      const usedSymbols  = new Set(leadingSlots.map((p: any) => p.symbol));
      // 2) 나머지 슬롯은 다른 섹터 BUY+A/B 상위 종목으로 채움 (섹터당 1개)
      const fillPicks: any[] = [];
      for (const p of buyPicks) {
        if (fillPicks.length >= 3) break;
        if (usedSymbols.has(p.symbol)) continue;
        if (!usedSectors.has(p.sector ?? "")) {
          fillPicks.push(p);
          usedSectors.add(p.sector ?? "");
        }
      }
      const diversifiedList = [...leadingSlots, ...fillPicks].slice(0, 5);

      // Step 1
      const s1sig = verdictSignal(verdict);
      const s1: StepStatus = {
        signal: s1sig,
        title: "시장 진입 여부",
        summary: `종합 판단 ${verdict} · 게이트 점수 ${gate.avg_score?.toFixed(2) ?? "—"}`,
        detail: `시장 체제·게이트 점수·스크리닝 결과를 통합한 최종 신호입니다. 현재 ${verdict}${
          s1sig === "GO" ? " — 신규 진입 가능 환경입니다." :
          s1sig === "CAUTION" ? " — 신규 진입보다 기존 포지션 관리에 집중하세요." :
          " — 시장 환경이 불리합니다."
        }`,
        action: s1sig === "GO" ? "정상 투자 진행 → 다음 단계 확인" :
                s1sig === "CAUTION" ? "기존 포지션 유지, 신규 매수 자제" :
                "즉시 포지션 정리, 현금 보유 극대화",
        proceed: s1sig !== "STOP",
      };

      // Step 2
      const s2sig: Signal = rName === "risk_on" ? "GO" : rName === "neutral" ? "GO" : rName === "risk_off" ? "CAUTION" : "STOP";
      const s2: StepStatus = {
        signal: s2sig,
        title: "체제 & 투자 비중",
        summary: `${rName.replace("_", " ")} · 권장 ${regSize.pct}${clabel ? ` · 사이클 ${clabel}` : ""}`,
        detail: `현재 ${rName.replace("_", " ")} 체제입니다. 5개 센서(VIX·Trend·Breadth·Credit·YieldCurve) 가중합으로 판정됩니다. 총 자산의 ${regSize.pct}를 주식에 배분하세요.${clabel ? ` 현재 ${clabel} 구간으로 ${leadingEtfs.join(", ")} 섹터가 선행 중입니다.` : ""}`,
        action: `투자 비중 ${regSize.pct} 설정 — ${regSize.desc}`,
        proceed: s2sig !== "STOP",
      };

      // Step 3
      const s3sig: Signal = buyPicks.length >= 3 ? "GO" : buyPicks.length >= 1 ? "CAUTION" : "STOP";
      const diversifiedSymbols = diversifiedList.map((p: any) => p.symbol).join(", ");
      // 섹터 분포 요약 (중복 섹터 경고용)
      const sectorCounts: Record<string, number> = {};
      diversifiedList.forEach((p: any) => { const s = p.sector ?? "기타"; sectorCounts[s] = (sectorCounts[s] ?? 0) + 1; });
      const hasSectorConcentration = Object.values(sectorCounts).some((n) => n >= 2);
      const sectorSummary = Object.entries(sectorCounts).map(([s, n]) => `${s}${n >= 2 ? `×${n}` : ""}`).join(" · ");
      const s3: StepStatus = {
        signal: s3sig,
        title: "종목 선택",
        summary: `BUY A·B등급 ${buyPicks.length}개${alignedPicks.length > 0 ? ` · 선행섹터 ${alignedPicks.length}개` : ""} · ${diversifiedSymbols || "없음"}`,
        detail: `${clabel ? `현재 ${clabel} 구간 — ${leadingEtfs.join(", ")} 선행 중. ` : ""}${
          alignedPicks.length > 0
            ? `선행 섹터 우선 + 섹터 분산 적용: ${diversifiedSymbols || "없음"}`
            : `오늘 BUY A·B 종목 중 선행 섹터(${leadingEtfs.join(", ") || "—"}) 소속이 없어 섹터 분산만 적용: ${diversifiedSymbols || "없음"}`
        }${hasSectorConcentration ? ` ⚠ 동일 섹터 2개 이상 포함(${sectorSummary}) — 직접 분산 조정 권장` : ` (${sectorSummary})`}`,
        action: diversifiedList.length > 0
          ? `분산 후보 → ${diversifiedSymbols}${hasSectorConcentration ? " ⚠ 섹터 편중 확인" : ""}`
          : buyPicks.length >= 1 ? "조건 충족 종목 부족 — 상위 종목 탭 직접 확인" : "조건 종목 없음 — 대기",
        proceed: s3sig !== "STOP",
      };

      // Step 4
      const buySummaries = summaries.filter((s: any) => s.recommendation === "BUY");
      const s4: StepStatus = {
        signal: buySummaries.length >= 2 ? "GO" : "CAUTION",
        title: "AI 검증",
        summary: `AI BUY 추천 ${buySummaries.length}개 · 전체 ${summaries.length}개`,
        detail: `GPT-4o가 분석한 ${summaries.length}개 종목 중 BUY 추천은 ${buySummaries.length}개입니다. thesis(투자 근거)가 납득되고, bear cases(하락 리스크)를 감수할 수 있는 종목만 최종 선정하세요.`,
        action: "thesis 납득 + bear case 감수 가능 종목만 최종 선정",
        proceed: true,
      };

      // Step 5
      const var95Warn = var95 !== null && Math.abs(var95) > 0.02;
      const mddWarn   = mdd  !== null && Math.abs(mdd)  > 0.1;
      const s5sig: Signal = var95Warn && mddWarn ? "STOP" : var95Warn || mddWarn ? "CAUTION" : "GO";
      const s5: StepStatus = {
        signal: s5sig,
        title: "리스크 관리",
        summary: `손절선 ${stopLoss} · VaR95 ${var95 != null ? `${(var95 * 100).toFixed(2)}%` : "—"} · MDD ${mdd != null ? `${(mdd * 100).toFixed(2)}%` : "—"}`,
        detail: `권장 손절선 ${stopLoss}. VaR95 ${var95 != null ? `${(var95 * 100).toFixed(2)}%` : "미집계"}${var95Warn ? " ⚠ 경고(2% 초과)" : ""}. MDD ${mdd != null ? `${(mdd * 100).toFixed(2)}%` : "미집계"}${mddWarn ? " ⚠ 경고" : ""}.`,
        action: `각 종목 진입 시 ${stopLoss} 손절 주문 설정 필수`,
        proceed: s5sig !== "STOP",
      };

      // Step 6
      const spyGo   = spyDir === "bullish" && spyPct !== null && spyPct >= 55;
      const spyCaut = spyDir === "bullish" && spyPct !== null && spyPct < 55;
      const s6sig: Signal = spyGo ? "GO" : "CAUTION";
      const qqqStr = qqq ? `QQQ ${qqq.direction === "bullish" ? "강세" : "약세"} ${Math.round((qqq.probability ?? 0.5) * 100)}%` : "";
      const s6: StepStatus = {
        signal: s6sig,
        title: "타이밍 확인",
        summary: `SPY ${spyDir === "bullish" ? "강세" : spyDir === "bearish" ? "약세" : "—"} ${spyPct ?? "—"}% · ${qqqStr || "QQQ —"}`,
        detail: `LightGBM 다음 주 SPY 방향 예측: ${spyDir === "bullish" ? `강세 (${spyPct}%)` : spyDir === "bearish" ? `약세 (${spyPct}%)` : "없음"}. ${spyGo ? "진입 타이밍 양호." : spyCaut ? "강세지만 확률 낮음 — 분할 매수 고려." : "약세 예측 — 대기 권고."}`,
        action: spyGo ? "지금 분산 진입 실행" : spyCaut ? "분할 매수 — 30~50% 우선 진입" : "1~2주 대기 후 재확인",
        proceed: true,
      };

      const newSteps = [s1, s2, s3, s4, s5, s6];
      setSteps(newSteps);
      setRegimeName(rName);
      setCycleLabel(clabel);
      setReportDate(report.analysis_date ?? "");
      setReports(reportsRes.status === "fulfilled" ? reportsRes.value : []);
      setSectorData(sector);
      if (aiRes.status === "fulfilled") {
        const list: any[] = aiRes.value?.summaries ?? (Array.isArray(aiRes.value) ? aiRes.value : []);
        const m: Record<string, any> = {};
        list.forEach((s: any) => { if (s.ticker) m[s.ticker] = s; });
        setAiMap(m);
      }

      // 종합 판단 계산
      const stops = newSteps.filter((s) => s.signal === "STOP").length;
      const cauts = newSteps.filter((s) => s.signal === "CAUTION").length;
      const ov: Signal = stops > 0 ? "STOP" : cauts >= 2 ? "CAUTION" : "GO";
      setOverall(ov);

      // 오늘 할 일 생성
      const todayActions: string[] = [];
      if (ov === "GO") {
        todayActions.push(
          diversifiedList.length > 0
            ? `섹터 분산 후보 — ${diversifiedSymbols}${hasSectorConcentration ? " (⚠ 동일 섹터 편중 확인)" : ""}`
            : buyPicks.length > 0
            ? `BUY A·B등급 ${buyPicks.length}개 중 3~5종목 직접 분산 선택`
            : "스크리닝 조건 종목 부족 — 다음 분석 실행 후 재확인"
        );
        todayActions.push(`투자 비중 ${regSize.pct} 유지, 각 종목 손절선 ${stopLoss} 설정`);
        if (spyGo) todayActions.push("SPY 강세 예측 — 지금 분산 진입 실행");
        else todayActions.push("SPY 확률 낮음 — 분할 매수(50% 우선 진입)");
      } else if (ov === "CAUTION") {
        todayActions.push("신규 매수 자제 — 기존 포지션만 유지");
        todayActions.push(`손절선 ${stopLoss}보다 5% 좁게 설정, 이익 실현 우선`);
        todayActions.push("다음 분석 결과 확인 후 재진입 여부 결정");
      } else {
        todayActions.push("전체 포지션 정리 — 현금 비중 극대화");
        todayActions.push("신규 매수 금지 — 다음 분석까지 대기");
        todayActions.push("시장 안정 신호 확인 후 재검토");
      }
      setActions(todayActions);
    });
  }, [market]);

  const loading = steps[0].signal === "LOADING";

  return (
    <div className="space-y-3 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#262112", color: "#726b58" }}>
          <FlagIcon market={market === "KR" ? "KR" : "US"} size={14} />{" "}{market === "KR" ? "KOSPI" : "S&P 500"}
        </span>
        <h1 className="text-base font-bold text-white">투자 의사결정 워크플로우</h1>
        {!loading && (
          <span className="text-[12px] px-2 py-0.5 rounded font-bold"
            style={{ background: "#ffb02022", color: "#ffb020", border: "1px solid #ffb02044" }}>
            LIVE
          </span>
        )}
      </div>

      {loading && (
        <div className="rounded-xl p-8 text-center" style={{ background: "#111009", border: "1px solid #262112" }}>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>데이터 로딩 중…</p>
        </div>
      )}

      {/* 종합 판단 히어로 — 최상단 */}
      {!loading && (
        <HeroVerdict
          overall={overall}
          actions={actions}
          regimeName={regimeName}
          cycleLabel={cycleLabel}
          date={reportDate}
        />
      )}

      {/* 6개 신호 그리드 */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {steps.map((step, i) => (
            <SignalCard
              key={i}
              step={i + 1}
              status={step}
              isOpen={openStep === i}
              onClick={() => setOpenStep(openStep === i ? null : i)}
              linkHref={STEP_META[i].linkHref}
              linkLabel={STEP_META[i].linkLabel}
            />
          ))}
        </div>
      )}

      {/* 진행 흐름 표시 */}
      {!loading && (
        <div className="flex items-center gap-1 px-1">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center gap-1">
              <div
                className="w-2 h-2 rounded-full cursor-pointer"
                style={{ background: SIG_COLOR[s.signal] }}
                onClick={() => setOpenStep(openStep === i ? null : i)}
              />
              {i < steps.length - 1 && (
                <div className="w-6 h-px" style={{ background: s.proceed ? SIG_COLOR[s.signal] + "44" : "#262112" }} />
              )}
            </div>
          ))}
          <span className="ml-2 text-[12px]" style={{ color: "var(--text-faint)" }}>
            워크플로우 {steps.filter((s) => s.signal === "GO").length}/6 정상
          </span>
        </div>
      )}

      {/* 매수 전 체크리스트 */}
      {!loading && (
        <PreTradeChecklist
          steps={steps}
          overall={overall}
          reports={reports}
          sector={sectorData}
          market={market}
          aiMap={aiMap}
          regimeName={regimeName}
        />
      )}

      <p className="text-[12px] text-center" style={{ color: "var(--text-faint)" }}>
        본 도구는 투자 참고용이며 수익을 보장하지 않습니다. 모든 투자 결정은 본인 책임입니다.
      </p>
    </div>
  );
}
