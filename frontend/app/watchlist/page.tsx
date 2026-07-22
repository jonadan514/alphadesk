"use client";

import { useEffect, useState, useCallback } from "react";
import { X, Info, Pencil } from "lucide-react";
import StockTechPanel from "@/src/components/StockTechPanel";

interface Candidate {
  market: string;
  symbol: string;
  name: string | null;
  market_cap: number | null;
  sector: string | null;
  piotroski: number | null;
  debt_ratio: number | null;
  interest_coverage: number | null;
  cfo_positive_count: number;
  red_flags: string[];
  regime_fit: "growth" | "dividend" | "neutral";
  roe: number | null;
  rel_3m: number | null;
  rel_6m: number | null;
  fit_score: number | null;
  data_notes?: { interest?: string; debt?: string };
}

// ── 프로토타입 팔레트 (이 페이지 한정) ───────────────────────────────────────
// globals.css의 공용 토큰과는 별도로, 워치리스트 페이지에서만 새 팔레트를 시험한다.
const PAGE_BG   = "#12151a";
const PANEL_BG  = "#191d24";  // 모달 등 주요 표면
const INSET_BG  = "#14181f";  // 패널 안의 중첩 카드
const INPUT_BG  = "#10131a";
const HOVER_BG  = "#1c212a";
const BORDER    = "#262b34";  // 정적 카드/구분선
const BORDER_CTRL = "#313846"; // 체크박스·인풋 등 조작 요소 테두리

const TEXT_PRIMARY   = "#e6e8eb";
const TEXT_BODY      = "#c4c9d0";
const TEXT_SECONDARY = "#aab0b8";
const TEXT_MUTED     = "#7d848c";
const TEXT_FAINT     = "#565c66";

const ACCENT  = "#34c98a"; // 브랜드 그린 = "양호" 시맨틱과 통일
const GOOD    = ACCENT;
const WARN    = "#facc15";
const CAUTION = "#f97316";
const BAD     = "#e0654f";
const BLUE    = "#60a5fa";
const PURPLE  = "#a78bfa";

const MONO = 'ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", monospace';

// 지표가 null일 때 "-" 대신 사유 표시 (무차입=좋음, 자본잠식=주의)
const NOTE_COLOR: Record<string, string> = {
  "무차입": GOOD,
  "자본잠식(음수 자본)": CAUTION,
  "금융업 제외": TEXT_MUTED,
  "데이터 없음": TEXT_FAINT,
};
function MetricOrNote({ value, note, format }: { value: number | null; note?: string; format: (v: number) => string }) {
  if (value != null) return <span style={{ color: TEXT_SECONDARY, fontVariantNumeric: "tabular-nums" }}>{format(value)}</span>;
  if (note) return <span style={{ color: NOTE_COLOR[note] ?? TEXT_FAINT, fontSize: 11 }}>{note}</span>;
  return <span style={{ color: TEXT_FAINT }}>-</span>;
}
interface WatchItem {
  id: number;
  market: string;
  symbol: string;
  name: string | null;
  note: string | null;
  added_at: string;
}
interface NarrativeBrief {
  story: string;
  catalysts: string[];
  risks: string[];
  sentiment: "HOT" | "WARM" | "COLD";
  sentiment_reason: string;
  sources: string[];
  cached_at: string;
  prev_sentiment?: "HOT" | "WARM" | "COLD" | null;
  trend?: "up" | "down" | "flat" | null;
}

// ── 지표 설명 ─────────────────────────────────────────────────────────────────
const INDICATOR_INFO = {
  fit: {
    title: "시장 적합 점수 (0~100)",
    desc: "함정 필터 통과 종목을 '지금 시장에서 살 만한 순서'로 줄 세운 점수입니다. 품질 40점(Piotroski·ROE·이자보상) + 모멘텀 35점(3·6개월 지수 대비 상대수익률) + 체제 정합 25점(현재 장세와 종목 성격의 궁합)으로 구성되며, 시장별 상위 50종목만 후보에 올라옵니다.",
    levels: [
      { range: "70점~", color: GOOD, label: "우수 — 재무 탄탄 + 시장이 사주는 중" },
      { range: "55~70점", color: WARN, label: "양호 — 일부 축이 아쉬움" },
      { range: "~55점", color: TEXT_SECONDARY, label: "보통 — 후보 중 하위권" },
    ],
  },
  fscore: {
    title: "Piotroski F-Score (0~9)",
    desc: "수익성·레버리지·운영효율 9가지 항목을 각 1점씩 채점한 재무 건전성 점수입니다.",
    levels: [
      { range: "7~9점", color: GOOD, label: "우수 — 재무 상태 탄탄" },
      { range: "5~6점", color: WARN, label: "보통 — 무난한 수준" },
      { range: "0~4점", color: BAD, label: "취약 — 스크리닝 제외" },
    ],
  },
  debt: {
    title: "부채비율 (총부채/자기자본)",
    desc: "기업이 자기자본 대비 얼마나 많은 부채를 쓰는지 나타냅니다. 낮을수록 재무가 안정적입니다. (금융업 제외)",
    levels: [
      { range: "~100%", color: GOOD, label: "안정" },
      { range: "100~150%", color: WARN, label: "보통" },
      { range: "150~200%", color: CAUTION, label: "주의" },
      { range: "200% 초과", color: BAD, label: "스크리닝 제외" },
    ],
  },
  interest: {
    title: "이자보상배율 (EBIT/이자비용)",
    desc: "영업이익으로 이자를 몇 배 낼 수 있는지 나타냅니다. 1배 미만이면 영업이익으로 이자도 못 내는 좀비기업입니다.",
    levels: [
      { range: "5x 이상", color: GOOD, label: "안전" },
      { range: "3~5x", color: WARN, label: "보통" },
      { range: "1~3x", color: CAUTION, label: "주의" },
      { range: "1x 미만", color: BAD, label: "스크리닝 제외" },
    ],
  },
  regime: {
    title: "시장 체제 적합도",
    desc: "현재 시장 흐름(성장장/배당장)에서 이 종목이 어느 전략에 더 어울리는지를 나타냅니다.",
    levels: [
      { range: "성장", color: BLUE, label: "고성장 — 매출/EPS 성장률 높음" },
      { range: "배당", color: GOOD, label: "배당 중심 — 배당수익률 2% 이상" },
      { range: "중립", color: TEXT_SECONDARY, label: "뚜렷한 특성 없음" },
    ],
  },
};

// ── Helpers ─────────────────────────────────────────────────────────────────
const FMT_CAP_US = (n: number) =>
  n >= 1e12 ? `$${(n / 1e12).toFixed(1)}T` : n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B` : `$${(n / 1e6).toFixed(0)}M`;
const FMT_CAP_KR = (n: number) =>
  n >= 1e12 ? `${(n / 1e12).toFixed(1)}조` : `${(n / 1e8).toFixed(0)}억`;
function formatCap(market: string, cap: number | null) {
  if (!cap) return "-";
  return market === "KR" ? FMT_CAP_KR(cap) : FMT_CAP_US(cap);
}

function PiotroskiBadge({ score }: { score: number | null }) {
  if (score === null) return <span style={{ color: TEXT_FAINT }}>-</span>;
  const color = score >= 7 ? GOOD : score >= 5 ? WARN : BAD;
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, borderRadius: 4, padding: "1px 6px", fontSize: 12, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
      {score}/9
    </span>
  );
}
function FitScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span style={{ color: TEXT_FAINT }}>-</span>;
  const color = score >= 70 ? GOOD : score >= 55 ? WARN : TEXT_SECONDARY;
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, borderRadius: 4, padding: "1px 7px", fontSize: 12, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
      {score.toFixed(0)}
    </span>
  );
}
function RegimeBadge({ fit }: { fit: string }) {
  const map: Record<string, { label: string; color: string }> = {
    growth:   { label: "성장", color: BLUE },
    dividend: { label: "배당", color: GOOD },
    neutral:  { label: "중립", color: TEXT_SECONDARY },
  };
  const { label, color } = map[fit] ?? map.neutral;
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, borderRadius: 4, padding: "1px 6px", fontSize: 11 }}>
      {label}
    </span>
  );
}

// ── 지표 설명 팝업 ────────────────────────────────────────────────────────────
function InfoModal({ info, onClose }: { info: typeof INDICATOR_INFO[keyof typeof INDICATOR_INFO]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.7)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 max-w-sm w-full space-y-3" style={{ background: PANEL_BG, border: `1px solid ${BORDER}` }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-bold" style={{ color: TEXT_PRIMARY }}>{info.title}</h3>
          <button onClick={onClose} style={{ color: TEXT_MUTED }}><X size={15} /></button>
        </div>
        <p className="text-[12px] leading-relaxed" style={{ color: TEXT_SECONDARY }}>{info.desc}</p>
        <div className="space-y-1.5">
          {info.levels.map((l) => (
            <div key={l.range} className="flex items-center gap-2">
              <span className="text-[11px] font-bold w-16 shrink-0" style={{ color: l.color }}>{l.range}</span>
              <span className="text-[11px]" style={{ color: TEXT_MUTED }}>{l.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 네러티브 브리프 (Perplexity 실시간 검색) ─────────────────────────────────
const SENTIMENT_STYLE: Record<string, { label: string; color: string; emoji: string }> = {
  HOT:  { label: "시장 관심 높음", color: BAD, emoji: "🔥" },
  WARM: { label: "꾸준한 관심",    color: WARN, emoji: "🌤" },
  COLD: { label: "시장 관심 밖",   color: BLUE, emoji: "❄️" },
};

function NarrativeSection({ c }: { c: Candidate }) {
  const [brief, setBrief]     = useState<NarrativeBrief | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setPending(false);
      try {
        const params = new URLSearchParams({ market: c.market, symbol: c.symbol });
        const res = await fetch(`/api/watchlist/narrative?${params}`);
        const data = await res.json();
        if (cancelled) return;
        if (res.status === 404 && data.pending) { setPending(true); return; }
        if (!res.ok) throw new Error(data.error ?? "요청 실패");
        setBrief(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "네러티브를 불러오지 못했어요");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [c.market, c.symbol]);

  const sent = brief ? (SENTIMENT_STYLE[brief.sentiment] ?? SENTIMENT_STYLE.WARM) : null;

  return (
    <div className="px-5">
      <div className="rounded-xl p-3 space-y-2.5" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
        <p className="text-[10px] uppercase tracking-widest" style={{ color: TEXT_FAINT }}>네러티브 브리프</p>

        {loading && (
          <p className="text-[12px] animate-pulse" style={{ color: TEXT_MUTED }}>불러오는 중...</p>
        )}
        {pending && !loading && (
          <p className="text-[12px]" style={{ color: TEXT_MUTED }}>
            아직 네러티브가 생성되지 않았어요. 다음 일간 분석(매일 아침 자동 실행) 후 표시돼요.
          </p>
        )}
        {error && !loading && (
          <p className="text-[12px]" style={{ color: BAD }}>{error}</p>
        )}

        {brief && !loading && (
          <>
            {sent && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-bold px-2 py-0.5 rounded" style={{ background: sent.color + "20", color: sent.color, border: `1px solid ${sent.color}40` }}>
                  {sent.emoji} {sent.label}
                </span>
                {brief.trend === "up" && brief.prev_sentiment && (
                  <span className="text-[11px] font-bold px-2 py-0.5 rounded" style={{ background: BAD + "20", color: BAD, border: `1px solid ${BAD}40` }}>
                    ▲ 관심도 상승 ({brief.prev_sentiment}→{brief.sentiment})
                  </span>
                )}
                {brief.trend === "down" && brief.prev_sentiment && (
                  <span className="text-[11px] font-bold px-2 py-0.5 rounded" style={{ background: BLUE + "20", color: BLUE, border: `1px solid ${BLUE}40` }}>
                    ▼ 관심도 하락 ({brief.prev_sentiment}→{brief.sentiment})
                  </span>
                )}
                {brief.sentiment_reason && (
                  <span className="text-[11px]" style={{ color: TEXT_MUTED }}>{brief.sentiment_reason}</span>
                )}
              </div>
            )}

            <p className="text-[12px] leading-relaxed" style={{ color: TEXT_BODY }}>{brief.story}</p>

            {brief.catalysts.length > 0 && (
              <div>
                <p className="text-[10px] font-bold mb-1" style={{ color: GOOD }}>▲ 다가오는 촉매</p>
                {brief.catalysts.map((t, i) => (
                  <p key={i} className="text-[11px] leading-relaxed pl-2" style={{ color: TEXT_SECONDARY }}>· {t}</p>
                ))}
              </div>
            )}
            {brief.risks.length > 0 && (
              <div>
                <p className="text-[10px] font-bold mb-1" style={{ color: BAD }}>▼ 스토리가 깨지는 경우</p>
                {brief.risks.map((t, i) => (
                  <p key={i} className="text-[11px] leading-relaxed pl-2" style={{ color: TEXT_SECONDARY }}>· {t}</p>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-1" style={{ borderTop: `1px solid ${BORDER}` }}>
              <span className="text-[10px]" style={{ color: TEXT_FAINT }}>
                최근 1주 뉴스 기반 GPT 분석 · 참고용 · {brief.cached_at.slice(0, 10)} 갱신
              </span>
              {brief.sources.length > 0 && (
                <span className="flex gap-1.5">
                  {brief.sources.slice(0, 3).map((url, i) => (
                    <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="text-[10px] underline" style={{ color: TEXT_FAINT }}>
                      출처{i + 1}
                    </a>
                  ))}
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── 종목 정성 체크리스트 (종목별 독립 저장) ──────────────────────────────────
interface ChecklistItem { id: string; text: string; checked: boolean }

function ChecklistSection({ c }: { c: Candidate }) {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/watchlist/checklist?market=${c.market}&symbol=${c.symbol}`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setItems(d.items ?? []); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [c.market, c.symbol]);

  const toggle = (id: string) => {
    const next = items.map((it) => (it.id === id ? { ...it, checked: !it.checked } : it));
    setItems(next);
    fetch("/api/watchlist/checklist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ market: c.market, symbol: c.symbol, items: next }),
    }).catch(() => {});
  };

  if (loading) return <div className="h-20 rounded-xl animate-pulse" style={{ background: INSET_BG }} />;

  const checkedCount = items.filter((it) => it.checked).length;

  return (
    <div className="rounded-xl p-3 space-y-1.5" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
      <div className="flex items-center justify-between mb-0.5">
        <p className="text-[10px] uppercase tracking-widest" style={{ color: TEXT_FAINT }}>정성 체크</p>
        <span className="text-[11px]" style={{ color: checkedCount === items.length && items.length > 0 ? GOOD : TEXT_FAINT }}>
          {checkedCount}/{items.length}
        </span>
      </div>
      {items.map((it) => (
        <button
          key={it.id}
          onClick={() => toggle(it.id)}
          className="w-full flex items-start gap-2 text-left py-1"
          style={{ background: "transparent", border: "none", cursor: "pointer" }}
        >
          <span
            className="mt-0.5 shrink-0 w-3.5 h-3.5 rounded flex items-center justify-center"
            style={{
              background: it.checked ? GOOD + "33" : PANEL_BG,
              border: `1.5px solid ${it.checked ? GOOD : BORDER_CTRL}`,
            }}
          >
            {it.checked && <span style={{ color: GOOD, fontSize: 9, fontWeight: 900 }}>✓</span>}
          </span>
          <span className="text-[12px] leading-snug" style={{ color: it.checked ? TEXT_MUTED : TEXT_BODY }}>
            {it.text}
          </span>
        </button>
      ))}
    </div>
  );
}

// ── 종목 상세 팝업 ────────────────────────────────────────────────────────────
function DetailModal({ c, inList, inTopPicks, note, onAdd, onSaveNote, onClose }: {
  c: Candidate; inList: boolean; inTopPicks: boolean; note: string | null;
  onAdd: () => void; onSaveNote: (note: string) => void; onClose: () => void;
}) {
  const [editingNote, setEditingNote] = useState(false);
  const [noteDraft, setNoteDraft] = useState(note ?? "");
  const coverColor = (v: number | null) => {
    if (!v) return TEXT_MUTED;
    return v >= 5 ? GOOD : v >= 3 ? WARN : v >= 1 ? CAUTION : BAD;
  };
  const debtColor = (v: number | null) => {
    if (!v) return TEXT_MUTED;
    return v <= 100 ? GOOD : v <= 150 ? WARN : v <= 200 ? CAUTION : BAD;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.75)" }} onClick={onClose}>
      <div className="rounded-2xl w-full max-w-md space-y-4 max-h-[88vh] overflow-y-auto" style={{ background: PANEL_BG, border: `1px solid ${BORDER}` }} onClick={(e) => e.stopPropagation()}>
        {/* 헤더 */}
        <div className="flex items-start justify-between px-5 pt-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-bold px-2 py-0.5 rounded" style={{ background: c.market === "US" ? BLUE + "20" : BAD + "20", color: c.market === "US" ? BLUE : BAD }}>{c.market}</span>
              <RegimeBadge fit={c.regime_fit} />
              {inTopPicks && (
                <span title="오늘 종목 분석 상위 종목에 포함"
                  style={{ background: ACCENT + "20", color: ACCENT, border: `1px solid ${ACCENT}40`, borderRadius: 4, padding: "1px 6px", fontSize: 10, fontWeight: 700 }}>
                  ⭐ 오늘픽
                </span>
              )}
            </div>
            <h2 className="text-xl font-black" style={{ color: TEXT_PRIMARY, fontFamily: MONO, letterSpacing: "-0.01em" }}>{c.symbol}</h2>
            {c.name && <p className="text-[13px] mt-0.5" style={{ color: TEXT_SECONDARY }}>{c.name}</p>}
            {c.sector && <p className="text-[11px] mt-0.5" style={{ color: TEXT_MUTED }}>{c.sector} · {formatCap(c.market, c.market_cap)}</p>}
          </div>
          <button onClick={onClose} className="p-1" style={{ color: TEXT_MUTED }}><X size={16} /></button>
        </div>

        {/* 적합점수 + 모멘텀 */}
        <div className="px-5">
          <div className="rounded-xl p-3 flex items-center justify-between" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
            <div>
              <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: TEXT_FAINT }}>시장 적합 점수</p>
              <p className="text-2xl font-black" style={{ color: c.fit_score != null ? (c.fit_score >= 70 ? GOOD : c.fit_score >= 55 ? WARN : TEXT_SECONDARY) : TEXT_FAINT, fontFamily: MONO, fontVariantNumeric: "tabular-nums" }}>
                {c.fit_score != null ? c.fit_score.toFixed(0) : "-"}<span className="text-sm font-normal" style={{ color: TEXT_FAINT }}>/100</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: TEXT_FAINT }}>지수 대비 상대수익률</p>
              <p className="text-[12px]" style={{ color: TEXT_SECONDARY }}>
                3개월 <span style={{ color: c.rel_3m != null ? (c.rel_3m >= 0 ? GOOD : BAD) : TEXT_FAINT, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{c.rel_3m != null ? `${c.rel_3m > 0 ? "+" : ""}${c.rel_3m}%` : "-"}</span>
              </p>
              <p className="text-[12px]" style={{ color: TEXT_SECONDARY }}>
                6개월 <span style={{ color: c.rel_6m != null ? (c.rel_6m >= 0 ? GOOD : BAD) : TEXT_FAINT, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{c.rel_6m != null ? `${c.rel_6m > 0 ? "+" : ""}${c.rel_6m}%` : "-"}</span>
              </p>
            </div>
          </div>
        </div>

        {/* 지표 그리드 */}
        <div className="px-5 grid grid-cols-2 gap-3">
          {/* F-Score */}
          <div className="rounded-xl p-3" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: TEXT_FAINT }}>Piotroski F-Score</p>
            <p className="text-2xl font-black" style={{ color: c.piotroski != null ? (c.piotroski >= 7 ? GOOD : c.piotroski >= 5 ? WARN : BAD) : TEXT_FAINT, fontFamily: MONO, fontVariantNumeric: "tabular-nums" }}>
              {c.piotroski ?? "-"}<span className="text-sm font-normal" style={{ color: TEXT_FAINT }}>/9</span>
            </p>
            <p className="text-[10px] mt-1" style={{ color: TEXT_MUTED }}>
              {c.piotroski != null ? (c.piotroski >= 7 ? "재무 우수" : c.piotroski >= 5 ? "보통 수준" : "취약") : "데이터 없음"}
            </p>
          </div>

          {/* 부채비율 */}
          <div className="rounded-xl p-3" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: TEXT_FAINT }}>부채비율</p>
            {c.debt_ratio != null ? (
              <p className="text-2xl font-black" style={{ color: debtColor(c.debt_ratio), fontFamily: MONO, fontVariantNumeric: "tabular-nums" }}>{c.debt_ratio}%</p>
            ) : (
              <p className="text-[15px] font-black leading-7" style={{ color: NOTE_COLOR[c.data_notes?.debt ?? ""] ?? TEXT_FAINT }}>
                {c.data_notes?.debt ?? "-"}
              </p>
            )}
            <p className="text-[10px] mt-1" style={{ color: TEXT_MUTED }}>
              {c.data_notes?.debt === "자본잠식(음수 자본)" ? "자사주 매입 등으로 자기자본이 음수 — 원인 확인 필요" : "총부채 / 자기자본"}
            </p>
          </div>

          {/* 이자보상배율 */}
          <div className="rounded-xl p-3" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: TEXT_FAINT }}>이자보상배율</p>
            {c.interest_coverage != null ? (
              <p className="text-2xl font-black" style={{ color: coverColor(c.interest_coverage), fontFamily: MONO, fontVariantNumeric: "tabular-nums" }}>{c.interest_coverage.toFixed(1)}x</p>
            ) : (
              <p className="text-[15px] font-black leading-7" style={{ color: NOTE_COLOR[c.data_notes?.interest ?? ""] ?? TEXT_FAINT }}>
                {c.data_notes?.interest ?? "-"}
              </p>
            )}
            <p className="text-[10px] mt-1" style={{ color: TEXT_MUTED }}>
              {c.data_notes?.interest === "무차입" ? "이자비용 없음 — 빚 없이 운영 중" : "영업이익 / 이자비용"}
            </p>
          </div>

          {/* 영업현금흐름 */}
          <div className="rounded-xl p-3" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: TEXT_FAINT }}>영업현금흐름</p>
            <p className="text-2xl font-black" style={{ color: c.cfo_positive_count >= 2 ? GOOD : c.cfo_positive_count === 1 ? WARN : BAD, fontFamily: MONO, fontVariantNumeric: "tabular-nums" }}>
              {c.cfo_positive_count}/2
            </p>
            <p className="text-[10px] mt-1" style={{ color: TEXT_MUTED }}>최근 2년 중 플러스 연도</p>
          </div>
        </div>

        {/* 체제 설명 */}
        <div className="px-5">
          <div className="rounded-xl p-3" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
            <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: TEXT_FAINT }}>시장 체제 적합도</p>
            <div className="flex items-center gap-2">
              <RegimeBadge fit={c.regime_fit} />
              <span className="text-[12px]" style={{ color: TEXT_SECONDARY }}>
                {c.regime_fit === "growth" ? "매출/EPS 성장률 높음 — 성장장에 유리" :
                 c.regime_fit === "dividend" ? "배당수익률 2% 이상 — 배당장에 유리" :
                 "뚜렷한 성장·배당 특성 없음"}
              </span>
            </div>
          </div>
        </div>

        {/* 추세·모멘텀 차트 */}
        <div className="px-5">
          <StockTechPanel market={c.market} symbol={c.symbol} />
        </div>

        {/* 네러티브 브리프 */}
        <NarrativeSection c={c} />

        {/* 정성 체크 (구 투자 워크북) */}
        <div className="px-5">
          <ChecklistSection c={c} />
        </div>

        {/* 매수 이유 메모 — 워치리스트에 추가된 종목만 */}
        {inList && (
          <div className="px-5">
            <div className="rounded-xl p-3" style={{ background: INSET_BG, border: `1px solid ${BORDER}` }}>
              <p className="text-[10px] uppercase tracking-widest mb-1.5" style={{ color: TEXT_FAINT }}>매수 이유 메모</p>
              {editingNote ? (
                <div className="flex gap-1.5">
                  <input
                    value={noteDraft}
                    onChange={(e) => setNoteDraft(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { onSaveNote(noteDraft.trim()); setEditingNote(false); } if (e.key === "Escape") setEditingNote(false); }}
                    placeholder="담은 이유, 지켜볼 포인트…"
                    autoFocus
                    className="flex-1 px-2.5 py-1.5 rounded-lg text-[12px] outline-none"
                    style={{ background: INPUT_BG, color: TEXT_PRIMARY, border: `1px solid ${BORDER_CTRL}` }}
                  />
                  <button onClick={() => { onSaveNote(noteDraft.trim()); setEditingNote(false); }}
                    className="px-3 rounded-lg text-[12px] font-bold" style={{ background: ACCENT + "18", color: ACCENT, border: `1px solid ${ACCENT}33` }}>저장</button>
                </div>
              ) : (
                <button onClick={() => setEditingNote(true)} className="text-[12px] text-left w-full" style={{ color: note ? TEXT_SECONDARY : TEXT_FAINT, background: "transparent", border: "none", cursor: "pointer" }}>
                  {note || "+ 메모 추가 — 왜 담았는지 기록해두세요"}
                </button>
              )}
            </div>
          </div>
        )}

        {/* 버튼 */}
        <div className="px-5 pb-5">
          <button
            onClick={onAdd}
            disabled={inList}
            className="w-full py-2.5 rounded-xl text-[13px] font-bold transition-opacity disabled:opacity-40"
            style={{ background: inList ? PANEL_BG : ACCENT + "18", color: inList ? TEXT_FAINT : ACCENT, border: `1px solid ${inList ? BORDER : ACCENT + "33"}` }}>
            {inList ? "이미 워치리스트에 추가됨" : "+ 내 워치리스트에 추가"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 컬럼 헤더 (툴팁) ─────────────────────────────────────────────────────────
function ColHeader({ label, infoKey, onInfo }: {
  label: string;
  infoKey?: keyof typeof INDICATOR_INFO;
  onInfo?: (key: keyof typeof INDICATOR_INFO) => void;
}) {
  return (
    <th style={{ padding: "8px 10px", textAlign: "left", fontWeight: 500, whiteSpace: "nowrap" }}>
      <span style={{ display: "flex", alignItems: "center", gap: 4, color: TEXT_MUTED, fontSize: 12 }}>
        {label}
        {infoKey && onInfo && (
          <button onClick={(e) => { e.stopPropagation(); onInfo(infoKey); }} style={{ color: TEXT_FAINT, lineHeight: 0 }}>
            <Info size={11} />
          </button>
        )}
      </span>
    </th>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function WatchlistPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [myList, setMyList]         = useState<WatchItem[]>([]);
  const [screened_at, setScreenedAt] = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const [tab, setTab]               = useState<"candidates" | "my">("candidates");
  const [marketFilter, setMarketFilter] = useState<"ALL" | "US" | "KR">("ALL");
  const [regimeFilter, setRegimeFilter] = useState<"ALL" | "growth" | "dividend" | "neutral">("ALL");
  const [addedSymbols, setAddedSymbols] = useState<Set<string>>(new Set());
  const [selected, setSelected]     = useState<Candidate | null>(null);
  const [infoKey, setInfoKey]       = useState<keyof typeof INDICATOR_INFO | null>(null);

  const [topPicks, setTopPicks] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cRes, mRes] = await Promise.all([
        fetch("/api/watchlist/candidates"),
        fetch("/api/watchlist/my"),
      ]);
      const cData = await cRes.json();
      const mData: WatchItem[] = await mRes.json();
      setCandidates(cData.candidates ?? []);
      setScreenedAt(cData.screened_at ?? null);
      setMyList(mData);
      setAddedSymbols(new Set(mData.map((w) => `${w.market}:${w.symbol}`)));
    } finally {
      setLoading(false);
    }
  }, []);

  // 오늘의 종목 분석(top-picks) 등장 여부
  useEffect(() => {
    Promise.allSettled([
      fetch("/api/data/reports?limit=1").then((r) => r.json()),
      fetch("/api/data/kr/reports?limit=1").then((r) => r.json()),
    ]).then(([usRes, krRes]) => {
      const set = new Set<string>();
      if (usRes.status === "fulfilled") {
        ((usRes.value?.[0]?.picks ?? []) as { symbol?: string }[]).forEach((p) => {
          if (p.symbol) set.add(`US:${p.symbol}`);
        });
      }
      if (krRes.status === "fulfilled") {
        ((krRes.value?.[0]?.picks ?? []) as { symbol?: string }[]).forEach((p) => {
          if (p.symbol) set.add(`KR:${p.symbol}`);
        });
      }
      setTopPicks(set);
    });
  }, []);

  // 오늘 관심도 상승(COLD→WARM/HOT 등) 종목
  const [shifts, setShifts] = useState<{ market: string; symbol: string; name?: string | null; prev_sentiment: string; sentiment: string }[]>([]);
  useEffect(() => {
    fetch("/api/watchlist/narrative-shifts")
      .then((r) => r.json())
      .then((d) => setShifts(d.shifts ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const addToWatchlist = async (c: Candidate) => {
    await fetch("/api/watchlist/my", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ market: c.market, symbol: c.symbol, name: c.name }),
    });
    load();
  };
  const removeFromWatchlist = async (id: number) => {
    await fetch(`/api/watchlist/my/${id}`, { method: "DELETE" });
    load();
  };

  // 메모 인라인 편집 (내 워치리스트 탭 목록용)
  const [editingNote, setEditingNote] = useState<number | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const saveNote = async (item: WatchItem) => {
    await fetch("/api/watchlist/my", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ market: item.market, symbol: item.symbol, name: item.name, note: noteDraft.trim() || null }),
    });
    setEditingNote(null);
    load();
  };

  // 상세 팝업에서의 메모 저장 (종목 클릭 → 팝업 내 메모)
  const saveNoteFromModal = async (c: Candidate, note: string) => {
    await fetch("/api/watchlist/my", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ market: c.market, symbol: c.symbol, name: c.name, note: note || null }),
    });
    load();
  };

  const filtered = candidates.filter((c) => {
    if (marketFilter !== "ALL" && c.market !== marketFilter) return false;
    if (regimeFilter !== "ALL" && c.regime_fit !== regimeFilter) return false;
    return true;
  });

  const statStyle: React.CSSProperties = {
    background: INSET_BG, border: `1px solid ${BORDER}`, borderRadius: 8,
    padding: "10px 16px", textAlign: "center",
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px", color: TEXT_PRIMARY, background: PAGE_BG, minHeight: "100vh" }}>
      {/* 팝업들 */}
      {selected && (
        <DetailModal
          c={selected}
          inList={addedSymbols.has(`${selected.market}:${selected.symbol}`)}
          inTopPicks={topPicks.has(`${selected.market}:${selected.symbol}`)}
          note={myList.find((w) => w.market === selected.market && w.symbol === selected.symbol)?.note ?? null}
          onAdd={() => addToWatchlist(selected)}
          onSaveNote={(note) => saveNoteFromModal(selected, note)}
          onClose={() => setSelected(null)}
        />
      )}
      {infoKey && (
        <InfoModal info={INDICATOR_INFO[infoKey]} onClose={() => setInfoKey(null)} />
      )}

      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, fontFamily: MONO, letterSpacing: "-0.01em", color: TEXT_PRIMARY }}>워치리스트</h1>
        <p style={{ color: TEXT_MUTED, fontSize: 13, marginTop: 4 }}>
          함정 필터 통과 → 시장 적합 점수(품질·모멘텀·체제) 시장별 상위 50종목
          {screened_at && (
            <span style={{ marginLeft: 8, color: TEXT_FAINT }}>(스크리닝: {screened_at.slice(0, 10)})</span>
          )}
        </p>
      </div>

      {/* 관심도 상승 배너 */}
      {shifts.length > 0 && (
        <div style={{ marginBottom: 20, borderRadius: 8, padding: "10px 14px", background: BAD + "12", border: `1px solid ${BAD}33` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: BAD }}>▲ 오늘 관심도 상승</span>
            {shifts.map((s) => (
              <span key={`${s.market}:${s.symbol}`} style={{ fontSize: 12, color: TEXT_PRIMARY }}>
                <span style={{ color: s.market === "US" ? BLUE : BAD, fontWeight: 600 }}>
                  {s.market === "KR" ? (s.name || s.symbol) : s.symbol}
                </span>
                <span style={{ color: TEXT_MUTED }}> ({s.prev_sentiment}→{s.sentiment})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 통계 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "후보 종목", value: candidates.length },
          { label: "내 워치리스트", value: myList.length },
          { label: "성장 후보", value: candidates.filter((c) => c.regime_fit === "growth").length },
          { label: "배당 후보", value: candidates.filter((c) => c.regime_fit === "dividend").length },
        ].map(({ label, value }) => (
          <div key={label} style={statStyle}>
            <div style={{ fontSize: 22, fontWeight: 700, color: ACCENT, fontFamily: MONO, fontVariantNumeric: "tabular-nums" }}>{value}</div>
            <div style={{ fontSize: 12, color: TEXT_MUTED, marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* 탭 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, borderBottom: `1px solid ${BORDER}`, paddingBottom: 12 }}>
        {(["candidates", "my"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: tab === t ? ACCENT + "20" : "transparent",
            color: tab === t ? ACCENT : TEXT_MUTED,
            border: `1px solid ${tab === t ? ACCENT + "40" : BORDER_CTRL}`,
            borderRadius: 6, padding: "6px 16px", fontSize: 13, cursor: "pointer",
          }}>
            {t === "candidates" ? `스크리닝 후보 (${filtered.length})` : `내 워치리스트 (${myList.length})`}
          </button>
        ))}
      </div>

      {/* ── 스크리닝 후보 탭 ── */}
      {tab === "candidates" && (
        <>
          <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
            {(["ALL", "US", "KR"] as const).map((m) => (
              <button key={m} onClick={() => setMarketFilter(m)} style={{
                background: marketFilter === m ? BLUE + "20" : "transparent",
                color: marketFilter === m ? BLUE : TEXT_MUTED,
                border: `1px solid ${marketFilter === m ? BLUE + "40" : BORDER_CTRL}`,
                borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer",
              }}>{m === "ALL" ? "전체" : m}</button>
            ))}
            <div style={{ width: 1, background: BORDER_CTRL, margin: "0 4px" }} />
            {(["ALL", "growth", "dividend", "neutral"] as const).map((r) => (
              <button key={r} onClick={() => setRegimeFilter(r)} style={{
                background: regimeFilter === r ? PURPLE + "20" : "transparent",
                color: regimeFilter === r ? PURPLE : TEXT_MUTED,
                border: `1px solid ${regimeFilter === r ? PURPLE + "40" : BORDER_CTRL}`,
                borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer",
              }}>{r === "ALL" ? "전체" : r === "growth" ? "성장" : r === "dividend" ? "배당" : "중립"}</button>
            ))}
          </div>

          {loading ? (
            <div style={{ color: TEXT_MUTED, textAlign: "center", padding: 60 }}>불러오는 중...</div>
          ) : filtered.length === 0 ? (
            <div style={{ color: TEXT_MUTED, textAlign: "center", padding: 60 }}>
              {candidates.length === 0 ? "스크리닝 데이터 없음." : "필터 조건에 맞는 종목 없음."}
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <p style={{ fontSize: 11, color: TEXT_FAINT, marginBottom: 8 }}>행 클릭 시 상세 정보 · ⓘ 클릭 시 지표 설명</p>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                    <ColHeader label="마켓" />
                    <ColHeader label="티커" />
                    <ColHeader label="종목명" />
                    <ColHeader label="적합점수" infoKey="fit" onInfo={setInfoKey} />
                    <ColHeader label="시가총액" />
                    <ColHeader label="섹터" />
                    <ColHeader label="F-Score" infoKey="fscore" onInfo={setInfoKey} />
                    <ColHeader label="부채비율" infoKey="debt" onInfo={setInfoKey} />
                    <ColHeader label="이자보상" infoKey="interest" onInfo={setInfoKey} />
                    <ColHeader label="체제" infoKey="regime" onInfo={setInfoKey} />
                    <th style={{ padding: "8px 10px" }} />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => {
                    const key = `${c.market}:${c.symbol}`;
                    const inList = addedSymbols.has(key);
                    return (
                      <tr key={key}
                        onClick={() => setSelected(c)}
                        style={{ borderBottom: `1px solid ${BORDER}`, cursor: "pointer" }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = HOVER_BG)}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <td style={{ padding: "8px 10px" }}>
                          <span style={{ color: c.market === "US" ? BLUE : BAD, fontSize: 11, fontWeight: 600 }}>{c.market}</span>
                        </td>
                        <td style={{ padding: "8px 10px", fontWeight: 600, color: TEXT_PRIMARY, whiteSpace: "nowrap", fontFamily: MONO }}>
                          {c.symbol}
                          {topPicks.has(key) && (
                            <span title="오늘 종목 분석 상위 종목에 포함"
                              style={{ marginLeft: 6, background: ACCENT + "20", color: ACCENT, border: `1px solid ${ACCENT}40`, borderRadius: 4, padding: "1px 5px", fontSize: 10, fontWeight: 700, fontFamily: "inherit" }}>
                              오늘픽
                            </span>
                          )}
                        </td>
                        <td style={{ padding: "8px 10px", color: TEXT_SECONDARY, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name ?? "-"}</td>
                        <td style={{ padding: "8px 10px" }}><FitScoreBadge score={c.fit_score} /></td>
                        <td style={{ padding: "8px 10px", color: TEXT_SECONDARY, fontVariantNumeric: "tabular-nums" }}>{formatCap(c.market, c.market_cap)}</td>
                        <td style={{ padding: "8px 10px", color: TEXT_MUTED, fontSize: 11 }}>{c.sector ?? "-"}</td>
                        <td style={{ padding: "8px 10px" }}><PiotroskiBadge score={c.piotroski} /></td>
                        <td style={{ padding: "8px 10px" }}>
                          <MetricOrNote value={c.debt_ratio} note={c.data_notes?.debt} format={(v) => `${v}%`} />
                        </td>
                        <td style={{ padding: "8px 10px" }}>
                          <MetricOrNote value={c.interest_coverage} note={c.data_notes?.interest} format={(v) => v.toFixed(1) + "x"} />
                        </td>
                        <td style={{ padding: "8px 10px" }}><RegimeBadge fit={c.regime_fit} /></td>
                        <td style={{ padding: "8px 10px" }} onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => !inList && addToWatchlist(c)}
                            disabled={inList}
                            style={{
                              background: inList ? PANEL_BG : ACCENT + "20",
                              color: inList ? TEXT_FAINT : ACCENT,
                              border: `1px solid ${inList ? BORDER : ACCENT + "40"}`,
                              borderRadius: 4, padding: "3px 10px", fontSize: 11,
                              cursor: inList ? "default" : "pointer",
                            }}>
                            {inList ? "추가됨" : "+ 추가"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── 내 워치리스트 탭 ── */}
      {tab === "my" && (
        myList.length === 0 ? (
          <div style={{ color: TEXT_MUTED, textAlign: "center", padding: 60 }}>아직 추가한 종목이 없어요.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {myList.map((item) => (
              <div key={item.id} style={{ background: INSET_BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: "12px 16px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ color: item.market === "US" ? BLUE : BAD, fontSize: 11, fontWeight: 600, minWidth: 24 }}>{item.market}</span>
                  <span style={{ fontWeight: 700, fontSize: 15, minWidth: 60, fontFamily: MONO, color: TEXT_PRIMARY }}>{item.symbol}</span>
                  {topPicks.has(`${item.market}:${item.symbol}`) && (
                    <span title="오늘 종목 분석 상위 종목에 포함"
                      style={{ background: ACCENT + "20", color: ACCENT, border: `1px solid ${ACCENT}40`, borderRadius: 4, padding: "1px 6px", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
                      오늘픽
                    </span>
                  )}
                  <span style={{ color: TEXT_SECONDARY, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.name ?? ""}</span>
                  <span style={{ color: TEXT_FAINT, fontSize: 11 }}>{item.added_at.slice(0, 10)}</span>
                  <button onClick={() => removeFromWatchlist(item.id)} style={{ background: "transparent", color: TEXT_MUTED, border: `1px solid ${BORDER_CTRL}`, borderRadius: 4, padding: "2px 8px", fontSize: 11, cursor: "pointer" }}>삭제</button>
                </div>
                {/* 메모 */}
                <div style={{ marginTop: 8 }}>
                  {editingNote === item.id ? (
                    <div style={{ display: "flex", gap: 6 }}>
                      <input
                        value={noteDraft}
                        onChange={(e) => setNoteDraft(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") saveNote(item); if (e.key === "Escape") setEditingNote(null); }}
                        placeholder="담은 이유, 지켜볼 포인트… (예: AI 전력 수요 수혜, 2분기 실적 확인)"
                        autoFocus
                        style={{ flex: 1, background: INPUT_BG, color: TEXT_PRIMARY, border: `1px solid ${BORDER_CTRL}`, borderRadius: 6, padding: "6px 10px", fontSize: 12, outline: "none" }}
                      />
                      <button onClick={() => saveNote(item)} style={{ background: ACCENT + "18", color: ACCENT, border: `1px solid ${ACCENT}33`, borderRadius: 6, padding: "4px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>저장</button>
                      <button onClick={() => setEditingNote(null)} style={{ background: PANEL_BG, color: TEXT_MUTED, border: `1px solid ${BORDER_CTRL}`, borderRadius: 6, padding: "4px 10px", fontSize: 12, cursor: "pointer" }}>취소</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => { setEditingNote(item.id); setNoteDraft(item.note ?? ""); }}
                      style={{ display: "flex", alignItems: "center", gap: 6, background: "transparent", border: "none", cursor: "pointer", padding: 0, textAlign: "left" }}
                    >
                      <Pencil size={11} style={{ color: TEXT_FAINT, flexShrink: 0 }} />
                      <span style={{ color: item.note ? TEXT_SECONDARY : TEXT_FAINT, fontSize: 12 }}>
                        {item.note || "메모 추가 — 왜 담았는지 기록해두세요"}
                      </span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}
