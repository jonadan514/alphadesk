"use client";

import { useEffect, useState } from "react";
import FlagIcon from "@/src/components/FlagIcon";

interface StockRef {
  market: string;
  symbol: string;
  name?: string | null;
  fit_score?: number | null;
  path?: string;
  catalysts?: string[];
}
interface MarketWeek {
  index_chg_1w: number | null;
}
interface Briefing {
  week: string;
  generated_at: string;
  us: MarketWeek;
  kr: MarketWeek;
  watchlist: { total: number; added: StockRef[]; removed: StockRef[]; top: StockRef[]; has_prev: boolean };
  sentiment_heating: StockRef[];
  catalysts: StockRef[];
  gpt_comment: string;
}

function StockLabel({ s }: { s: StockRef }) {
  return (
    <span className="inline-flex items-center gap-1">
      <FlagIcon market={s.market as "US" | "KR"} size={11} />
      <span className="font-bold text-white">{s.market === "KR" ? (s.name || s.symbol) : s.symbol}</span>
    </span>
  );
}

function MarketRow({ label, m }: { label: string; m: MarketWeek }) {
  return (
    <div className="flex items-center gap-3 flex-wrap rounded-lg px-3 py-2" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
      <span className="text-[13px] font-bold text-white w-24 shrink-0">{label}</span>
      {m.index_chg_1w != null ? (
        <span className="text-[12px] font-bold" style={{ color: m.index_chg_1w >= 0 ? "#4ade80" : "#f87171" }}>
          주간 {m.index_chg_1w >= 0 ? "+" : ""}{m.index_chg_1w}%
        </span>
      ) : (
        <span className="text-[12px]" style={{ color: "var(--text-faint)" }}>—</span>
      )}
    </div>
  );
}

function BriefingCard({ b, defaultOpen }: { b: Briefing; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const wl = b.watchlist ?? { total: 0, added: [], removed: [], top: [], has_prev: false };

  return (
    <div className="bg-card rounded-xl overflow-hidden">
      <button className="w-full flex items-center gap-3 px-4 py-3 text-left" onClick={() => setOpen(!open)}>
        <span className="text-[14px] font-bold text-white">📋 {b.week} 주</span>
        <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{b.generated_at}</span>
        <span className="ml-auto text-[12px]" style={{ color: "#ffb020" }}>{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4" style={{ borderTop: "1px solid var(--border)" }}>
          {/* 시장 궤적 */}
          <div className="pt-3 space-y-1.5">
            <p className="text-[11px] font-bold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>지난주 시장</p>
            <MarketRow label="🇺🇸 S&P 500" m={b.us} />
            <MarketRow label="🇰🇷 KOSPI" m={b.kr} />
          </div>

          {/* GPT 총평 */}
          {b.gpt_comment && (
            <div className="rounded-xl p-3" style={{ background: "#ffb02008", border: "1px solid #ffb02022" }}>
              <p className="text-[11px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "#ffb020" }}>주간 총평</p>
              <p className="text-[12px] leading-relaxed whitespace-pre-line" style={{ color: "#a39c88" }}>{b.gpt_comment}</p>
            </div>
          )}

          {/* 워치리스트 변동 */}
          <div>
            <p className="text-[11px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "var(--text-muted)" }}>
              워치리스트 변동 <span style={{ color: "var(--text-faint)" }}>(후보 {wl.total}개)</span>
            </p>
            {!wl.has_prev ? (
              <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>첫 스냅샷 주간 — 다음 주부터 신규/탈락 비교가 표시돼요.</p>
            ) : wl.added.length === 0 && wl.removed.length === 0 ? (
              <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>변동 없음</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div className="rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid #ffb02022" }}>
                  <p className="text-[11px] font-bold mb-1" style={{ color: "#ffb020" }}>+ 신규 진입 ({wl.added.length})</p>
                  {wl.added.map((s) => (
                    <p key={`${s.market}:${s.symbol}`} className="text-[12px] py-0.5">
                      <StockLabel s={s} />
                      {s.fit_score != null && <span className="ml-1.5" style={{ color: "var(--text-muted)" }}>적합 {s.fit_score}</span>}
                    </p>
                  ))}
                  {wl.added.length === 0 && <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>없음</p>}
                </div>
                <div className="rounded-lg p-2.5" style={{ background: "var(--bg-inset)", border: "1px solid #f8717122" }}>
                  <p className="text-[11px] font-bold mb-1" style={{ color: "#f87171" }}>− 탈락 ({wl.removed.length})</p>
                  {wl.removed.map((s) => (
                    <p key={`${s.market}:${s.symbol}`} className="text-[12px] py-0.5"><StockLabel s={s} /></p>
                  ))}
                  {wl.removed.length === 0 && <p className="text-[12px]" style={{ color: "var(--text-faint)" }}>없음</p>}
                </div>
              </div>
            )}
          </div>

          {/* 관심도 상승 */}
          {b.sentiment_heating?.length > 0 && (
            <div>
              <p className="text-[11px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "var(--text-muted)" }}>이번 주 달아오른 종목</p>
              <div className="flex flex-wrap gap-2">
                {b.sentiment_heating.map((s) => (
                  <span key={`${s.market}:${s.symbol}`} className="text-[12px] px-2 py-1 rounded-lg"
                    style={{ background: "#f8717112", border: "1px solid #f8717133" }}>
                    <StockLabel s={s} /> <span style={{ color: "#f87171" }}>{s.path}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 다가오는 촉매 */}
          {b.catalysts?.length > 0 && (
            <div>
              <p className="text-[11px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "var(--text-muted)" }}>
                내 워치리스트 — 다가오는 촉매
              </p>
              <div className="space-y-1.5">
                {b.catalysts.map((s) => (
                  <div key={`${s.market}:${s.symbol}`} className="rounded-lg px-3 py-2" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
                    <StockLabel s={s} />
                    {(s.catalysts ?? []).map((c, i) => (
                      <p key={i} className="text-[12px] mt-0.5 pl-1" style={{ color: "var(--text-muted)" }}>▲ {c}</p>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function BriefingPage() {
  const [briefings, setBriefings] = useState<Briefing[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/briefing")
      .then((r) => r.json())
      .then((d) => setBriefings(d.briefings ?? []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-3 max-w-3xl">
      <div>
        <h1 className="text-base font-bold text-white">주간 브리핑</h1>
        <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>
          매주 월요일 아침, 지난주를 돌아보고 이번 주를 준비하는 문서 — 시장 궤적 · 워치리스트 변동 · 관심도 흐름 · 촉매
        </p>
      </div>

      {loading ? (
        <div className="h-24 rounded-xl animate-pulse" style={{ background: "#111009" }} />
      ) : briefings.length === 0 ? (
        <div className="bg-card rounded-xl p-6 text-center">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>아직 브리핑이 없어요.</p>
          <p className="text-[12px] mt-1" style={{ color: "var(--text-faint)" }}>
            매주 일요일 밤 워치리스트 스크리닝 후 자동 생성됩니다. 지금 만들려면:
            GitHub → Actions → Weekly Watchlist Screen → Run workflow
          </p>
        </div>
      ) : (
        briefings.map((b, i) => <BriefingCard key={b.week} b={b} defaultOpen={i === 0} />)
      )}
    </div>
  );
}
