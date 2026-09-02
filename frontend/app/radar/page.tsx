"use client";

import { useEffect, useState, useCallback } from "react";
import { themeName } from "@/src/lib/themeNames";

// globals.css의 앱 전역 토큰을 그대로 쓴다 (워치리스트 페이지와 같은 터미널·앰버 룩).
const ACCENT = "var(--accent)";
const ACCENT_SOFT = "rgba(255,176,32,0.14)";
const GOOD = "var(--good)";
const GOOD_SOFT = "rgba(74,222,128,0.14)";
const DANGER = "var(--danger)";
const DANGER_SOFT = "rgba(248,113,113,0.14)";
const MUTED = "var(--text-muted)";
const MUTED_SOFT = "rgba(139,130,113,0.14)";
const FAINT = "var(--text-faint)";
const MONO = 'ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", monospace';

type Arrow = "up2" | "up1" | "flat" | "down" | "na" | null;

interface ThemeSignal {
  theme_id: string;
  news_count: number | null;
  news_baseline: number | null;
  news_ratio: number | null;
  news_arrow: Arrow;
  earn_members: number | null;
  earn_improved: number | null;
  earn_insufficient: number | null;
  earn_ratio: number | null;
  earn_arrow: Arrow;
  earn_as_of: string | null;
  price_median_ret: number | null;
  price_index_ret: number | null;
  price_excess: number | null;
  price_arrow: Arrow;
  label: string | null;
  member_count: number | null;
}

interface Member {
  ticker: string;
  stage: string | null;
  evidence: string | null;
  linkage: string;
  confidence: string;
  flagged: number;
  other_themes: string[];
}

// SPEC §6.2 - 순위가 아니라 편집 방침. "조용히 좋아짐"이 맨 위인 이유는
// 뉴스만 봐서는 못 찾는 정보라서.
const LABEL_ORDER = ["조용히 좋아짐", "바닥 통과 가능", "새로 부상", "관심 강화", "과열 경계", "약화"];
const LABEL_NOTE: Record<string, string> = {
  "조용히 좋아짐": "뉴스는 잠잠하거나 줄었는데 실적은 실제로 개선된 테마.",
  "바닥 통과 가능": "뉴스도 주가도 안 좋은데 실적은 개선된 테마 - 시장이 아직 못 따라잡았을 가능성.",
  "새로 부상": "뉴스가 급증했지만 실적은 아직 안 나온 테마.",
  "관심 강화": "뉴스·실적·주가가 다 같은 방향으로 움직이는 테마.",
  "과열 경계": "뉴스·주가는 뜨거운데 실적은 식은 테마.",
  "약화": "세 축 다 하락한 테마.",
};

function arrowGlyph(a: Arrow): string {
  if (a === "up2") return "↑↑";
  if (a === "up1") return "↑";
  if (a === "flat") return "→";
  if (a === "down") return "↓";
  return "–";
}
function arrowColors(a: Arrow): { fg: string; bg: string } {
  if (a === "up2" || a === "up1") return { fg: GOOD, bg: GOOD_SOFT };
  if (a === "down") return { fg: DANGER, bg: DANGER_SOFT };
  if (a === "flat") return { fg: MUTED, bg: MUTED_SOFT };
  return { fg: FAINT, bg: "transparent" };
}
function pct(n: number | null, digits = 1): string {
  if (n == null) return "-";
  const v = (n * 100).toFixed(digits);
  return `${n >= 0 ? "+" : ""}${v}%`;
}
function isMoving(a: Arrow): boolean {
  return a === "up2" || a === "up1" || a === "down";
}

function ArrowChip({ axis, arrow }: { axis: string; arrow: Arrow }) {
  const { fg, bg } = arrowColors(arrow);
  return (
    <div className="flex w-14 shrink-0 flex-col items-center gap-0.5 rounded-lg py-1.5" style={{ background: bg }}>
      <span className="text-[10px]" style={{ color: FAINT }}>{axis}</span>
      <span className="text-[17px] font-bold" style={{ color: fg, fontFamily: MONO }}>{arrowGlyph(arrow)}</span>
    </div>
  );
}

function LabelBadge({ label }: { label: string }) {
  return (
    <span
      className="ml-auto shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-bold"
      style={{ background: ACCENT_SOFT, color: ACCENT }}
    >
      {label}
    </span>
  );
}

const LINKAGE_STYLE: Record<string, { label: string; fg: string; bg: string }> = {
  direct: { label: "주력", fg: "#4ade80", bg: "rgba(74,222,128,0.14)" },
  partial: { label: "일부", fg: "#6fb3b8", bg: "rgba(111,179,184,0.14)" },
  peripheral: { label: "간접", fg: FAINT, bg: "transparent" },
};
function LinkageBadge({ linkage }: { linkage: string }) {
  const s = LINKAGE_STYLE[linkage] ?? { label: linkage, fg: MUTED, bg: "transparent" };
  return (
    <span
      className="whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ background: s.bg, color: s.fg, border: s.bg === "transparent" ? "1px solid var(--border)" : "none" }}
    >
      {s.label}
    </span>
  );
}

function MembersTable({ members, loading }: { members: Member[]; loading: boolean }) {
  if (loading) return <div className="py-4 text-[12px]" style={{ color: MUTED }}>불러오는 중...</div>;
  if (members.length === 0) return <div className="py-4 text-[12px]" style={{ color: MUTED }}>소속 기업 정보를 찾을 수 없습니다.</div>;

  return (
    <div className="overflow-x-auto rounded-lg" style={{ border: "1px solid var(--border)" }}>
      <table className="w-full text-[13px]" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--bg-inset)" }}>
            {["티커", "가치사슬 단계", "근거", "구분"].map((h) => (
              <th key={h} className="whitespace-nowrap px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wide" style={{ color: FAINT, borderBottom: "1px solid var(--border)" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.ticker} style={{ borderBottom: "1px solid var(--border)" }}>
              <td className="px-3 py-2 font-bold" style={{ fontFamily: MONO, color: "var(--num)" }}>{m.ticker}</td>
              <td className="px-3 py-2 align-top">
                <div className="flex flex-wrap gap-1">
                  {m.stage && (
                    <span className="whitespace-nowrap rounded-full px-2 py-0.5 text-[11px]" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: MUTED }}>
                      {m.stage}
                    </span>
                  )}
                  {m.other_themes.map((t) => (
                    <span key={t} className="whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ background: ACCENT_SOFT, color: ACCENT }}>
                      {themeName(t).ko}에도 소속
                    </span>
                  ))}
                </div>
              </td>
              <td className="max-w-[360px] px-3 py-2 align-top text-[12.5px]" style={{ color: MUTED }}>{m.evidence ?? "-"}</td>
              <td className="px-3 py-2 align-top">
                <LinkageBadge linkage={m.linkage} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ThemeCard({ signal }: { signal: ThemeSignal }) {
  const [open, setOpen] = useState(false);
  const [members, setMembers] = useState<Member[] | null>(null);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const { ko, en } = themeName(signal.theme_id);

  const toggle = useCallback(() => {
    setOpen((o) => !o);
    if (!members && !loadingMembers) {
      setLoadingMembers(true);
      fetch(`/api/radar/members?theme_id=${encodeURIComponent(signal.theme_id)}`)
        .then((r) => r.json())
        .then((d) => setMembers(d.members ?? []))
        .catch(() => setMembers([]))
        .finally(() => setLoadingMembers(false));
    }
  }, [members, loadingMembers, signal.theme_id]);

  return (
    <div className="mb-3 overflow-hidden rounded-2xl" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <button
        onClick={toggle}
        className="flex w-full flex-wrap items-center gap-4 px-4 py-3.5 text-left"
        style={{ cursor: "pointer" }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        <div className="flex min-w-[170px] shrink-0 flex-col gap-0.5">
          <span className="text-[16px] font-bold" style={{ color: "var(--text-primary)" }}>{ko}</span>
          <span className="text-[12px]" style={{ color: FAINT }}>{en}</span>
        </div>
        <div className="flex gap-2.5">
          <ArrowChip axis="뉴스" arrow={signal.news_arrow} />
          <ArrowChip axis="실적" arrow={signal.earn_arrow} />
          <ArrowChip axis="주가" arrow={signal.price_arrow} />
        </div>
        {signal.label && <LabelBadge label={signal.label} />}
        <span className="ml-auto shrink-0 text-[13px] transition-transform" style={{ color: FAINT, transform: open ? "rotate(90deg)" : "none" }}>▸</span>
      </button>

      {open && (
        <div className="px-4 pb-4" style={{ borderTop: "1px solid var(--border)" }}>
          <div className="my-3 grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
            <div className="rounded-lg px-3 py-2 text-[13px]" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: MUTED }}>
              {signal.earn_arrow === "na" ? (
                <>
                  실적 판정 보류(표본 부족)
                  {signal.earn_members != null && (
                    <span className="ml-1 text-[11px]" style={{ color: FAINT }}>
                      {signal.earn_members}개사 중 {signal.earn_improved}개 확인
                    </span>
                  )}
                </>
              ) : signal.earn_members != null ? (
                <>
                  <b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>
                    {signal.earn_members}개사 중 {signal.earn_improved}개
                  </b> 매출 개선
                  {signal.earn_as_of && <span className="ml-1 text-[11px]" style={{ color: FAINT }}>{signal.earn_as_of} 기준</span>}
                </>
              ) : "실적 데이터 없음"}
            </div>
            <div className="rounded-lg px-3 py-2 text-[13px]" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: MUTED }}>
              뉴스 이번 주 <b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>{signal.news_count ?? "-"}건</b>
              {" / "}4주 평균 <b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>{signal.news_baseline != null ? Math.round(signal.news_baseline) : "-"}건</b>
            </div>
            <div className="rounded-lg px-3 py-2 text-[13px]" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: MUTED }}>
              주가 중앙값 <b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>{pct(signal.price_median_ret)}</b>
              {signal.price_excess != null && <> · 지수 대비 <b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>{pct(signal.price_excess)}p</b></>}
            </div>
          </div>
          <MembersTable members={members ?? []} loading={loadingMembers} />
        </div>
      )}
    </div>
  );
}

export default function RadarPage() {
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [signals, setSignals] = useState<ThemeSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/radar")
      .then((r) => r.json())
      .then((d) => {
        setWeekStart(d.week_start ?? null);
        setSignals(d.signals ?? []);
      })
      .finally(() => setLoading(false));
  }, []);

  const labeled = signals.filter((s) => s.label);
  const unlabeledMoving = signals.filter(
    (s) => !s.label && (isMoving(s.news_arrow) || isMoving(s.earn_arrow) || isMoving(s.price_arrow))
  );

  const groups = LABEL_ORDER.map((label) => ({
    label,
    items: labeled.filter((s) => s.label === label),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="mx-auto max-w-4xl" style={{ color: "var(--text-primary)" }}>
      <div className="mb-2">
        <h1 className="text-[22px] font-bold" style={{ letterSpacing: "-0.01em" }}>이번 주 움직인 테마</h1>
        <p className="mt-1 max-w-[62ch] text-[14px]" style={{ color: MUTED }}>
          종합 점수도, 매수 추천도 없습니다. 뉴스·실적·주가 세 축을 각각 보여주고, 정해진 조합에만 이름을 붙입니다 — 나머지는 화살표로만 남겨둡니다.
        </p>
        {weekStart && (
          <p className="mt-2 text-[12px]" style={{ color: FAINT, fontFamily: MONO }}>
            기준 주 {weekStart} · 미국 시장 {signals.length}개 테마 중 {labeled.length}개 라벨 부여
          </p>
        )}
      </div>

      <div className="my-5 flex flex-wrap gap-4 rounded-xl px-4 py-3 text-[13px]" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: MUTED }}>
        <span><b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>↑↑</b> 강한 상승</span>
        <span><b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>↑</b> 상승</span>
        <span><b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>→</b> 보합</span>
        <span><b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>↓</b> 하락</span>
        <span><b style={{ fontFamily: MONO, color: "var(--text-primary)" }}>–</b> 판정 보류(표본 부족)</span>
      </div>

      {loading ? (
        <div className="py-16 text-center text-[13px]" style={{ color: MUTED }}>불러오는 중...</div>
      ) : signals.length === 0 ? (
        <div className="py-16 text-center text-[13px]" style={{ color: MUTED }}>아직 계산된 테마 신호가 없습니다.</div>
      ) : (
        <>
          {groups.map((g) => (
            <div key={g.label} className="mt-8">
              <div className="mb-1 flex items-baseline gap-2.5">
                <h2 className="text-[17px] font-bold">{g.label}</h2>
                <span className="text-[12px]" style={{ color: FAINT, fontFamily: MONO }}>{g.items.length}개 테마</span>
              </div>
              <p className="mb-3 max-w-[68ch] text-[13px]" style={{ color: MUTED }}>{LABEL_NOTE[g.label]}</p>
              {g.items.map((s) => <ThemeCard key={s.theme_id} signal={s} />)}
            </div>
          ))}

          {unlabeledMoving.length > 0 && (
            <div className="mt-8">
              <div className="mb-1 flex items-baseline gap-2.5">
                <h2 className="text-[17px] font-bold">라벨 없음 — 화살표만</h2>
                <span className="text-[12px]" style={{ color: FAINT, fontFamily: MONO }}>{unlabeledMoving.length}개 테마</span>
              </div>
              <p className="mb-3 max-w-[68ch] text-[13px]" style={{ color: MUTED }}>
                6개 조합 표에 안 맞으면 억지로 이름 붙이지 않습니다. 화살표만 보고 판단은 직접.
              </p>
              {unlabeledMoving.map((s) => <ThemeCard key={s.theme_id} signal={s} />)}
            </div>
          )}
        </>
      )}

      <div className="mt-12 border-t pt-5 text-[12px] leading-relaxed" style={{ borderColor: "var(--border)", color: FAINT }}>
        <p>이 화면이 하지 않는 것</p>
        <ul className="mt-1 list-disc pl-5">
          <li>종합 점수·등급 표시</li>
          <li>&ldquo;매수 추천&rdquo; / &ldquo;BUY&rdquo; / &ldquo;우선순위&rdquo; 류의 표현</li>
          <li>테마를 수익률 기대치로 정렬</li>
        </ul>
      </div>
    </div>
  );
}
