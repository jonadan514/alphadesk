"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import FlagIcon from "@/src/components/FlagIcon";

const VERDICT_COLOR: Record<string, string> = {
  GO: "#39ff8f", CAUTION: "#facc15", STOP: "#ef4444",
};

function Tag({ children, color = "#6e6e6e", bg = "#222" }: { children: React.ReactNode; color?: string; bg?: string }) {
  return (
    <span className="inline-block text-[11px] font-bold tracking-widest uppercase px-3 py-1 rounded-full mb-3"
      style={{ background: bg, color, border: `1px solid ${color}33` }}>
      {children}
    </span>
  );
}

function SectionHeader({ step, label, color, children }: { step: string; label: string; color: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <Tag color={color} bg={`${color}18`}>{step} {label}</Tag>
      <h2 className="text-2xl font-black text-white leading-snug">{children}</h2>
    </div>
  );
}

function GoTo({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href}
      className="inline-flex items-center gap-1.5 text-[12px] font-bold px-4 py-2 rounded-lg transition-all mt-4"
      style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
      {label} →
    </Link>
  );
}

export default function IntroPage() {
  const [gate, setGate]     = useState<any>(null);
  const [regime, setRegime] = useState<any>(null);
  const [picks, setPicks]   = useState<any[]>([]);
  const [positions, setPositions] = useState<any[]>([]);
  const [totalPnl, setTotalPnl]   = useState<number | null>(null);
  const [totalPct, setTotalPct]   = useState<number | null>(null);

  useEffect(() => {
    Promise.allSettled([
      fetch("/api/data/market-gate").then(r => r.json()),
      fetch("/api/data/regime").then(r => r.json()),
      fetch("/api/data/reports?limit=1").then(r => r.json()),
      fetch("/api/real/US/positions").then(r => r.json()),
      fetch("/api/real/KR/positions").then(r => r.json()),
    ]).then(([g, re, rep, usP, krP]) => {
      if (g.status   === "fulfilled") setGate(g.value);
      if (re.status  === "fulfilled") setRegime(re.value);
      if (rep.status === "fulfilled") setPicks((rep.value[0]?.picks ?? []).slice(0, 3));
      const usPos = usP.status === "fulfilled" ? usP.value.positions ?? [] : [];
      const krPos = krP.status === "fulfilled" ? krP.value.positions ?? [] : [];
      const all   = [
        ...usPos.map((p: any) => ({ ...p, mkt: "US" })),
        ...krPos.map((p: any) => ({ ...p, mkt: "KR" })),
      ];
      setPositions(all);
      const cost  = all.reduce((s: number, p: any) => s + p.cost_basis, 0);
      const value = all.reduce((s: number, p: any) => s + (p.market_value ?? p.cost_basis), 0);
      setTotalPnl(value - cost);
      setTotalPct(cost > 0 ? (value - cost) / cost : null);
    });
  }, []);

  const verdict      = gate?.gate ?? null;
  const verdictColor = VERDICT_COLOR[verdict ?? ""] ?? "#6e6e6e";
  const regimeLabel  = regime?.regime ?? null;

  const pnlPositive = (totalPnl ?? 0) >= 0;
  const pnlColor    = pnlPositive ? "#39ff8f" : "#ef4444";

  return (
    <div className="max-w-3xl space-y-2 pb-16">

      {/* ── Hero ─────────────────────────────────────────── */}
      <div className="rounded-2xl p-8 text-center"
        style={{ background: "linear-gradient(135deg,#39ff8f08,#111)", border: "1px solid #39ff8f22" }}>
        <div className="text-4xl font-black mb-2">
          Alpha<span style={{ color: "#39ff8f" }}>Desk</span>
        </div>
        <p className="text-lg font-semibold text-white mb-1">우리 가족의 투자 시스템</p>
        <p className="text-[14px] mb-6" style={{ color: "#a8a8a8" }}>
          감이 아닌 <strong className="text-white">데이터</strong>로,
          막연함이 아닌 <strong className="text-white">원칙</strong>으로 투자하는 방법
        </p>

        {/* Live verdict badge */}
        {verdict ? (
          <div className="inline-flex items-center gap-3 rounded-xl px-5 py-3 mb-4"
            style={{ background: `${verdictColor}12`, border: `1px solid ${verdictColor}44` }}>
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: verdictColor }} />
            <span className="text-[13px] font-bold" style={{ color: verdictColor }}>
              지금 이 순간 — 시장 판단: {verdict}
            </span>
            <span className="text-[12px]" style={{ color: "#6e6e6e" }}>
              ({regimeLabel?.replace("_", " ") ?? "—"})
            </span>
          </div>
        ) : (
          <div className="inline-block rounded-xl px-5 py-3 mb-4 animate-pulse"
            style={{ background: "#1c1c1c", border: "1px solid #2e2e2e", width: 280, height: 44 }} />
        )}

        <p className="text-[12px]" style={{ color: "#4a4a4a" }}>
          ↓ 아래에서 각 기능을 실제 데이터와 함께 살펴보세요
        </p>
      </div>

      {/* ── 왜 필요한가 ──────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <Tag>왜 만들었나</Tag>
        <h2 className="text-2xl font-black text-white mb-4">
          개인 투자자가 늘 <span style={{ color: "#ef4444" }}>지는 이유</span>
        </h2>
        <div className="space-y-2">
          {[
            ["📰", "뉴스·유튜브를 보고 감으로 사는데, 정작 왜 샀는지 설명할 수 없다"],
            ["😰", '"곧 오르겠지" 기다리다 손실이 눈덩이가 된다'],
            ["📊", "HTS·MTS에 숫자는 많은데 지금 사야 하는지 판단하기 어렵다"],
            ["🤷", "포트폴리오가 얼마나 위험한지, 어디서 무너질지 모른다"],
          ].map(([icon, text]) => (
            <div key={text} className="flex items-start gap-3 rounded-xl px-4 py-3"
              style={{ background: "#111", border: "1px solid #2e2e2e" }}>
              <span className="text-lg shrink-0">{icon}</span>
              <p className="text-[14px]" style={{ color: "#a8a8a8" }}>{text}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── ① 시장 체제 ──────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <SectionHeader step="①" label="시장 체제" color="#39ff8f">
          "지금 사도 되나?"를<br/>
          <span style={{ color: "#39ff8f" }}>자동으로 판단</span>합니다
        </SectionHeader>
        <p className="text-[14px] mb-4" style={{ color: "#a8a8a8" }}>
          VIX·추세·유동성 등 5개 센서를 종합해 매일 체제를 판별합니다.
          지금 이 순간의 실제 분석 결과입니다.
        </p>

        <div className="grid grid-cols-3 gap-3 mb-4">
          {[
            { v: "GO",      sub: "risk_on",        desc: "주식 비중 70~80%", color: "#39ff8f" },
            { v: "CAUTION", sub: "neutral",         desc: "주식 비중 50~60%", color: "#facc15" },
            { v: "STOP",    sub: "risk_off/crisis", desc: "현금이 전략",      color: "#ef4444" },
          ].map(({ v, sub, desc, color }) => (
            <div key={v} className="rounded-xl p-4 text-center relative overflow-hidden"
              style={{ background: verdict === v ? `${color}18` : "#111", border: `1px solid ${verdict === v ? color + "66" : "#2e2e2e"}` }}>
              {verdict === v && (
                <div className="absolute top-2 right-2 w-2 h-2 rounded-full animate-pulse" style={{ background: color }} />
              )}
              <p className="text-2xl font-black mb-1" style={{ color }}>{v}</p>
              <p className="text-[11px] font-bold mb-1" style={{ color }}>{sub}</p>
              <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{desc}</p>
              {verdict === v && (
                <p className="text-[11px] font-bold mt-2" style={{ color }}>← 오늘 실제</p>
              )}
            </div>
          ))}
        </div>

        {regime && (
          <div className="rounded-xl px-4 py-3 flex items-center justify-between"
            style={{ background: "#111", border: "1px solid #2e2e2e" }}>
            <span className="text-[13px]" style={{ color: "#6e6e6e" }}>오늘 체제 점수</span>
            <span className="text-lg font-black" style={{ color: verdictColor }}>
              {regime.weighted_score?.toFixed(2) ?? "—"}
            </span>
          </div>
        )}
        <GoTo href="/regime" label="시장 체제 직접 보기" />
      </div>

      {/* ── ② 종목 분석 ──────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <SectionHeader step="②" label="종목 분석" color="#60a5fa">
          "뭘 사야 하나?"<br/>
          <span style={{ color: "#60a5fa" }}>6가지 팩터 자동 스코어링</span>
        </SectionHeader>
        <p className="text-[14px] mb-4" style={{ color: "#a8a8a8" }}>
          S&P 500 전 종목을 매일 분석해 점수 순으로 줄 세웁니다.
          오늘 기준 상위 종목입니다.
        </p>

        {picks.length > 0 ? (
          <div className="space-y-2 mb-2">
            {picks.map((p: any) => (
              <div key={p.symbol} className="flex items-center gap-3 rounded-xl px-4 py-3"
                style={{ background: "#111", border: "1px solid #2e2e2e" }}>
                <span className="w-7 h-7 rounded-lg flex items-center justify-center text-[12px] font-black shrink-0"
                  style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
                  {p.grade}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="font-bold text-white text-[14px]">{p.symbol}</span>
                  {p.sector && <span className="ml-2 text-[12px]" style={{ color: "#6e6e6e" }}>{p.sector}</span>}
                </div>
                <span className="font-bold text-[14px]" style={{ color: "#39ff8f" }}>
                  {p.composite_score?.toFixed(1)}점
                </span>
                <span className="text-[12px] px-2 py-0.5 rounded"
                  style={{ background: "#202020", color: "#a8a8a8" }}>{p.action}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2 mb-2">
            {[1,2,3].map(i => (
              <div key={i} className="h-12 rounded-xl animate-pulse" style={{ background: "#111" }} />
            ))}
          </div>
        )}

        <div className="rounded-xl px-4 py-3" style={{ background: "#111", border: "1px solid #60a5fa22" }}>
          <p className="text-[12px]" style={{ color: "#6e6e6e" }}>
            💡 종목을 클릭하면 AI가 <strong className="text-white">투자 근거·목표주가·PER·리스크</strong>를 바로 설명합니다
          </p>
        </div>
        <GoTo href="/top-picks" label="종목 분석 직접 보기" />
      </div>

      {/* ── ③ 워크플로우 ─────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <SectionHeader step="③" label="워크플로우" color="#facc15">
          "매수 버튼 누르기 전"<br/>
          <span style={{ color: "#facc15" }}>6단계 자동 점검</span>
        </SectionHeader>
        <p className="text-[14px] mb-4" style={{ color: "#a8a8a8" }}>
          충동 매수를 막고, 조건이 맞을 때만 사게 도와줍니다.
          6개 신호가 모두 초록일 때만 매수를 진행합니다.
        </p>

        <div className="grid grid-cols-3 gap-2 mb-4">
          {[
            ["1", "마켓 게이트", "시장 진입 가능 여부"],
            ["2", "체제 & 비중",  "권장 주식 비중 제시"],
            ["3", "종목 선택",   "BUY 후보 자동 제안"],
            ["4", "AI 검증",    "AI BUY 추천 수 확인"],
            ["5", "리스크",     "VaR·MDD 경보 확인"],
            ["6", "타이밍",     "LightGBM 방향 예측"],
          ].map(([n, title, desc]) => (
            <div key={n} className="rounded-xl p-3" style={{ background: "#111", border: "1px solid #facc1522" }}>
              <p className="text-[11px] font-bold mb-1" style={{ color: "#facc15" }}>STEP {n}</p>
              <p className="text-[13px] font-bold text-white mb-0.5">{title}</p>
              <p className="text-[11px]" style={{ color: "#6e6e6e" }}>{desc}</p>
            </div>
          ))}
        </div>

        <div className="rounded-xl px-4 py-3" style={{ background: "#111", border: "1px solid #facc1533" }}>
          <p className="text-[12px]" style={{ color: "#a8a8a8" }}>
            💡 6개 신호 확인 후 → 티커·손절가를 입력하면{" "}
            <strong className="text-white">몇 주 살 수 있는지 자동 계산</strong>
          </p>
        </div>
        <GoTo href="/workflow" label="워크플로우 직접 보기" />
      </div>

      {/* ── ④ 리스크 관리 ────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <SectionHeader step="④" label="리스크 관리" color="#f97316">
          "언제 팔아야 하나"<br/>
          <span style={{ color: "#f97316" }}>원칙이 감정을 대신합니다</span>
        </SectionHeader>
        <div className="space-y-2">
          {[
            { icon: "🔴", color: "#ef4444", title: "손절 절대 원칙", desc: "매수가 대비 -7~8% 도달 시 이유 불문 즉시 매도. '곧 오르겠지'는 손실을 키운다." },
            { icon: "🎯", color: "#39ff8f", title: "목표가 도달",   desc: "AI 목표주가 도달 시 절반 또는 전량 매도 검토. 욕심은 수익을 돌려준다." },
            { icon: "⚡", color: "#facc15", title: "체제 악화",      desc: "마켓 게이트 STOP 또는 매수 이유(실적·사업) 소멸 시 가격 무관 매도." },
          ].map(({ icon, color, title, desc }) => (
            <div key={title} className="flex gap-3 rounded-xl px-4 py-3"
              style={{ background: "#111", border: `1px solid ${color}22` }}>
              <span className="text-xl shrink-0">{icon}</span>
              <div>
                <p className="font-bold text-white text-[14px] mb-1">{title}</p>
                <p className="text-[13px]" style={{ color: "#a8a8a8" }}>{desc}</p>
              </div>
            </div>
          ))}
        </div>
        <GoTo href="/risk" label="리스크 직접 보기" />
      </div>

      {/* ── ⑤ 포트폴리오 ─────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <SectionHeader step="⑤" label="포트폴리오" color="#a78bfa">
          "지금 어떻게 되고 있나"<br/>
          <span style={{ color: "#a78bfa" }}>실시간 손익 추적</span>
        </SectionHeader>
        <p className="text-[14px] mb-4" style={{ color: "#a8a8a8" }}>
          보유 종목을 등록하면 현재가를 자동으로 가져와 손익을 계산합니다.
          {positions.length > 0 ? " 현재 등록된 종목입니다." : " 아직 등록된 종목이 없습니다."}
        </p>

        {positions.length > 0 ? (
          <>
            <div className="rounded-xl px-4 py-3 mb-3 flex items-center justify-between"
              style={{ background: "#111", border: `1px solid ${pnlColor}33` }}>
              <span className="text-[13px]" style={{ color: "#6e6e6e" }}>총 손익</span>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-black" style={{ color: pnlColor }}>
                  {pnlPositive ? "+" : ""}{totalPnl?.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
                </span>
                {totalPct !== null && (
                  <span className="text-[13px] font-bold" style={{ color: pnlColor }}>
                    {pnlPositive ? "+" : ""}{(totalPct * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            <div className="space-y-2">
              {positions.map(pos => {
                const pct = pos.unrealized_pnl_pct;
                const c   = pct == null ? "#6e6e6e" : pct <= -0.06 ? "#ef4444" : pct < 0 ? "#f97316" : "#39ff8f";
                return (
                  <div key={`${pos.mkt}-${pos.symbol}`} className="flex items-center gap-3 rounded-xl px-4 py-2.5"
                    style={{ background: "#111", border: `1px solid ${pct != null && pct <= -0.06 ? "#ef444433" : "#2e2e2e"}` }}>
                    <FlagIcon market={pos.mkt} size={14} />
                    <span className="font-bold text-white text-[14px] flex-1">{pos.symbol}</span>
                    {pct != null && pct <= -0.06 && (
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded"
                        style={{ background: "#ef444422", color: "#ef4444" }}>손절임박</span>
                    )}
                    <span className="font-bold text-[14px]" style={{ color: c }}>
                      {pct != null ? `${pct >= 0 ? "+" : ""}${(pct * 100).toFixed(1)}%` : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <div className="rounded-xl px-4 py-6 text-center" style={{ background: "#111", border: "1px solid #2e2e2e" }}>
            <p className="text-[13px] mb-1" style={{ color: "#6e6e6e" }}>아직 등록된 종목이 없습니다</p>
            <p className="text-[12px]" style={{ color: "#4a4a4a" }}>포트폴리오 페이지에서 보유 종목을 추가하면 여기에 표시됩니다</p>
          </div>
        )}
        <GoTo href="/portfolio" label="포트폴리오 직접 보기" />
      </div>

      {/* ── 투자 철학 ─────────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <Tag>투자 철학</Tag>
        <h2 className="text-2xl font-black text-white mb-4">
          세계 최고 투자자 두 명의{" "}
          <span style={{ color: "#39ff8f" }}>원칙을 합쳤습니다</span>
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl p-4" style={{ background: "#111", border: "1px solid #39ff8f33" }}>
            <p className="text-[11px] font-bold tracking-widest mb-2" style={{ color: "#39ff8f" }}>PETER LYNCH</p>
            <p className="font-bold text-white text-[14px] mb-3">"이해할 수 있는 기업에만 투자하라"</p>
            <p className="text-[12px] mb-1" style={{ color: "#6e6e6e" }}>· PEG 비율로 성장 대비 저평가 발굴</p>
            <p className="text-[12px] mb-1" style={{ color: "#6e6e6e" }}>· 10루타: 10배 성장 기업 찾기</p>
            <p className="text-[12px]" style={{ color: "#6e6e6e" }}>· 이해 못하면 스킵</p>
          </div>
          <div className="rounded-xl p-4" style={{ background: "#111", border: "1px solid #60a5fa33" }}>
            <p className="text-[11px] font-bold tracking-widest mb-2" style={{ color: "#60a5fa" }}>WILLIAM O'NEIL</p>
            <p className="font-bold text-white text-[14px] mb-3">"손실은 짧게, 수익은 길게"</p>
            <p className="text-[12px] mb-1" style={{ color: "#6e6e6e" }}>· CANSLIM: EPS 성장 + 기관 매수</p>
            <p className="text-[12px] mb-1" style={{ color: "#6e6e6e" }}>· -7~8% 손절 규칙 절대 준수</p>
            <p className="text-[12px]" style={{ color: "#6e6e6e" }}>· 선행 섹터 선두 종목만 매수</p>
          </div>
        </div>
      </div>

      {/* ── 함께 하는 방법 ────────────────────────────────── */}
      <div className="rounded-2xl p-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <Tag>우리 투자 방식</Tag>
        <h2 className="text-2xl font-black text-white mb-4">
          함께 하면{" "}
          <span style={{ color: "#39ff8f" }}>더 잘할 수 있는</span> 이유
        </h2>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div className="rounded-xl p-4" style={{ background: "#111", border: "1px solid #39ff8f33" }}>
            <p className="text-[11px] font-bold tracking-widest mb-3" style={{ color: "#39ff8f" }}>ALPAHDESK (자동)</p>
            <div className="space-y-2">
              {["시장 체제 자동 판단", "종목 스코어링 매일 갱신", "손절임박 경보", "포지션 크기 역산", "전략 일지 기록"].map(t => (
                <p key={t} className="text-[13px]" style={{ color: "#a8a8a8" }}>✓ {t}</p>
              ))}
            </div>
          </div>
          <div className="rounded-xl p-4" style={{ background: "#111", border: "1px solid #a78bfa33" }}>
            <p className="text-[11px] font-bold tracking-widest mb-3" style={{ color: "#a78bfa" }}>우리 (최종 판단)</p>
            <div className="space-y-2">
              {["전략 포커스 결정", "최종 매수 승인", "목표·리스크 합의", "2주마다 같이 점검", "큰 그림 방향 조율"].map(t => (
                <p key={t} className="text-[13px]" style={{ color: "#a8a8a8" }}>✓ {t}</p>
              ))}
            </div>
          </div>
        </div>
        <div className="rounded-xl px-4 py-3 text-center" style={{ background: "#111", border: "1px solid #facc1533" }}>
          <p className="text-[13px]" style={{ color: "#a8a8a8" }}>
            <strong style={{ color: "#facc15" }}>중요한 원칙:</strong>{" "}
            시스템이 STOP이라고 하면 둘 다 동의해도 사지 않습니다.{" "}
            <strong className="text-white">규칙이 감정보다 앞섭니다.</strong>
          </p>
        </div>
      </div>

      {/* ── CTA ──────────────────────────────────────────── */}
      <div className="rounded-2xl p-8 text-center"
        style={{ background: "linear-gradient(135deg,#39ff8f0a,#111)", border: "1px solid #39ff8f33" }}>
        <p className="text-2xl font-black text-white mb-2">지금 바로 시작해볼까요?</p>
        <p className="text-[14px] mb-6" style={{ color: "#a8a8a8" }}>
          오늘 시장이 어떤 상태인지, 어떤 종목이 주목받는지 확인해보세요.
        </p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link href="/" className="text-[13px] font-bold px-5 py-2.5 rounded-xl"
            style={{ background: "#39ff8f", color: "#000" }}>
            시장 현황 보기 →
          </Link>
          <Link href="/workflow" className="text-[13px] font-bold px-5 py-2.5 rounded-xl"
            style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
            워크플로우 시작하기 →
          </Link>
        </div>
      </div>

    </div>
  );
}
