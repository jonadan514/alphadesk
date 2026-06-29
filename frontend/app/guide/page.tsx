"use client";

import Link from "next/link";
import FlagIcon from "@/src/components/FlagIcon";

const GUIDE_SECTIONS = [
  { href: "/workflow",  icon: "▶", label: "매수 체크",   desc: "종목 티커 입력 시 6개 시장 신호를 자동 점검해 GO/CAUTION/STOP 판정. 실제 매수 전 반드시 거치는 관문." },
  { href: "/",          icon: "⊡", label: "개요",        desc: "마켓 게이트·체제·상위 픽을 한 화면 요약. 오늘 시장 상태를 5초에 파악하는 시작점." },
  { href: "/regime",    icon: "▦", label: "시장 체제",   desc: "지금 시장이 강세/약세/위기 중 어느 단계인지 판단. 체제별 권장 주식 비중과 손절선 제공." },
  { href: "/sector",    icon: "⊞", label: "섹터 분석",   desc: "경기 사이클 단계와 지금 강한 업종 확인. 어느 분야 종목을 살지 방향을 잡는 탭." },
  { href: "/top-picks", icon: "★", label: "종목 분석",   desc: "팩터 점수로 자동 선별된 종목 목록. 종목 클릭 시 AI 투자 근거·목표가·리스크 요인 확인." },
  { href: "/risk",      icon: "⛨", label: "리스크",      desc: "포지션 계산기 — 얼마나 살지 수학적으로 계산. VaR·MDD로 위험도 점검." },
  { href: "/watchlist", icon: "🔖", label: "워치리스트",  desc: "재무 함정 필터(Piotroski·부채비율·이자보상배율 등)를 통과한 후보 종목 목록. 주간 자동 스크리닝." },
  { href: "/portfolio", icon: "◈", label: "포트폴리오",  desc: "내 실제 매수/매도 기록 관리. 첫 거래 시점을 100으로 기준점 삼아 벤치마크 대비 누적 성과를 추적." },
  { href: "/workbook",  icon: "◉", label: "투자 워크북", desc: "투자 전략 체크리스트·섹터/종목 선택 기준을 직접 관리. 매수 전 내 기준 점검 노트." },
];

const REGIME_ROWS = [
  { regime: "risk_on",  label: "Risk On (강세)",  meaning: "추세 상승, 변동성 낮음",     strategy: "공격적, 성장주 중심", stop: "-10%", equity: "70~80%" },
  { regime: "neutral",  label: "Neutral (중립)",  meaning: "혼조세, 방향 불명확",         strategy: "선별 매수, 균형",      stop: "-8%",  equity: "50~60%" },
  { regime: "risk_off", label: "Risk Off (약세)", meaning: "하락 압력, 변동성 상승",      strategy: "방어주·배당주 중심",   stop: "-5%",  equity: "30~40%" },
  { regime: "crisis",   label: "Crisis (위기)",   meaning: "급락 국면, 시스템 리스크",    strategy: "현금 최대화",           stop: "-3%",  equity: "10~20%" },
];

const STEPS = [
  { n: 1, label: "시장 진입 여부",   auto: "자동",   check: "마켓 게이트·종합 판단 신호 자동 표시",       go: "게이트 = GO" },
  { n: 2, label: "체제 & 투자 비중", auto: "자동",   check: "현재 체제 → 권장 주식 비중 자동 제시",       go: "risk_on · neutral" },
  { n: 3, label: "종목 선택",        auto: "자동",   check: "BUY A·B 선행섹터 분산 후보 자동 제안",       go: "BUY 종목 존재" },
  { n: 4, label: "AI 검증",          auto: "자동",   check: "AI BUY 추천 수·thesis 자동 표시",            go: "AI 분석 존재" },
  { n: 5, label: "리스크 관리",      auto: "자동",   check: "VaR·MDD·체제별 손절선 자동 경보",            go: "경보 없음" },
  { n: 6, label: "타이밍 확인",      auto: "자동",   check: "LightGBM SPY·KOSPI 방향 예측 자동 표시",     go: "강세 55%+" },
];

const AUTO_COLOR: Record<string, string> = {
  "자동": "#39ff8f",
  "반자동": "#facc15",
  "수동": "#9ca3af",
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[12px] font-bold uppercase tracking-widest mb-2" style={{ color: "var(--text-muted)" }}>
      {children}
    </h2>
  );
}
function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-card rounded-xl p-5 ${className}`}>{children}</div>;
}
function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span className="inline-block px-2 py-0.5 rounded-lg text-[12px] font-bold"
      style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}>
      {text}
    </span>
  );
}

export default function GuidePage() {
  return (
    <div className="space-y-6 max-w-5xl">

      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-base font-bold text-white">AlphaDesk 사용 설명서</h1>
          <Badge text="GUIDE" color="#39ff8f" />
        </div>
        <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          미국(S&amp;P 500) · 한국(KOSPI) 개인 투자자용 AI 주식 분석 대시보드
        </p>
        <Link
          href="/guide/detail"
          className="inline-flex items-center gap-1.5 mt-3 text-[12px] font-semibold rounded-xl px-3 py-1.5 transition-colors"
          style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
        >
          <span style={{ color: "#39ff8f" }}>◉</span>
          각 기능의 원리·해석법 세부 설명서 보기 →
        </Link>
      </div>

      {/* ── 완전 초보자 시작 가이드 ── */}
      <Card>
        <SectionTitle>📌 처음이라면 — 3분 안에 이해하기</SectionTitle>
        <p className="text-[12px] mb-4 leading-relaxed" style={{ color: "var(--text-muted)" }}>
          AlphaDesk는 <span className="text-white font-semibold">"지금 주식을 사도 되는가?"</span>를 단계별로 판단해주는 도구입니다.
          주식을 처음 시작하는 분도 아래 3단계만 따라하면 됩니다.
        </p>
        <div className="space-y-2 mb-5">
          {[
            {
              step: "STEP 1", color: "#39ff8f",
              title: "시장이 사기 좋은 상황인가? → 개요·시장 체제",
              body: "상단 마켓 게이트가 🟢 GO이면 사도 되는 시장입니다. 🟡 CAUTION이면 신중하게, 🔴 STOP이면 이번 달은 쉬세요. 체제가 risk_on일수록 공격적으로, crisis에 가까울수록 현금 비중을 높입니다.",
            },
            {
              step: "STEP 2", color: "#facc15",
              title: "어떤 종목을 살까? → 종목 분석",
              body: "종목 분석 탭에서 BUY·Grade A/B 종목을 확인하세요. 종목을 클릭하면 AI 투자 근거·목표가·PER·PBR·리스크 요인이 팝업으로 표시됩니다. 섹터 분석에서 지금 강한 업종(LEADING)의 종목을 우선 고려합니다.",
            },
            {
              step: "STEP 3", color: "#60a5fa",
              title: "얼마나, 어디서 살까? → 워크플로우 + 리스크",
              body: "워크플로우 탭에서 6개 시장 신호를 확인하고, 하단 체크리스트에 티커를 입력하면 매수 가능 여부가 자동 표시됩니다. 리스크 탭의 포지션 계산기에서 내 자산 대비 몇 주를 살지 계산하세요. 모든 항목이 초록(GO)이 되면 매수합니다. 매수 후 손절가(-7~8%)를 반드시 기억하세요.",
            },
          ].map(({ step, color, title, body }) => (
            <div key={step} className="rounded-xl p-4" style={{ background: "var(--bg-inset)", border: `1px solid ${color}33` }}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[12px] font-black px-2 py-0.5 rounded" style={{ background: `${color}22`, color }}>{step}</span>
                <p className="text-[13px] font-bold text-white">{title}</p>
              </div>
              <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>{body}</p>
            </div>
          ))}
        </div>

        <div className="rounded-xl p-4" style={{ background: "#39ff8f08", border: "1px solid #39ff8f22" }}>
          <p className="text-[12px] font-bold" style={{ color: "#39ff8f" }}>💡 가장 중요한 규칙 하나만 기억한다면</p>
          <p className="text-[13px] font-bold text-white mt-1">매수가 대비 -7~8% 하락하면 이유 불문 즉시 매도 (손절)</p>
          <p className="text-[12px] mt-1" style={{ color: "var(--text-muted)" }}>
            아무리 좋은 종목도 손절선 없이 보유하면 큰 손실로 이어집니다. 손절은 틀린 게 아니라 자산을 지키는 것입니다.
          </p>
        </div>
      </Card>

      {/* 시작하는 방법 */}
      <Card>
        <SectionTitle>시작하는 방법 — 바탕화면 배치 파일</SectionTitle>
        <div className="space-y-2 mb-4">
          {[
            { file: "AlphaDesk_전체시작.bat", color: "#39ff8f", desc: "권장 — 대시보드 + 미국 분석 완료 후 한국 분석 자동 시작 + 브라우저 오픈", tag: "추천" },
            { file: "AlphaDesk_대시보드.bat",  color: "#60a5fa", desc: "프론트엔드만 실행. 이전 분석 데이터 조회용 (분석 없음)", tag: "" },
            { file: "AlphaDesk_미국분석.bat",  color: "#a8a8a8", desc: "미국 분석만 단독 재실행", tag: "" },
            { file: "AlphaDesk_한국분석.bat",  color: "#a8a8a8", desc: "한국 분석만 단독 재실행", tag: "" },
          ].map(({ file, color, desc, tag }) => (
            <div key={file} className="flex items-start gap-3 rounded-xl p-3" style={{ background: "var(--bg-inset)", border: `1px solid ${color}33` }}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <code className="text-[12px] font-mono font-bold" style={{ color }}>{file}</code>
                  {tag && <Badge text={tag} color={color} />}
                </div>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>{desc}</p>
              </div>
            </div>
          ))}
        </div>

        <SectionTitle>전체시작 실행 순서</SectionTitle>
        <div className="space-y-1">
          {[
            "전체시작.bat 더블클릭",
            "탭 1: AlphaDesk Dashboard — Next.js 프론트엔드 (http://localhost:3000)",
            "탭 2: US then KR Analysis — 미국 분석 완료 후 한국 자동 시작",
            "6초 후 브라우저 자동 오픈 → 분석 중에도 이전 데이터 조회 가능",
            "분석 완료 후 F5 새로고침하면 최신 데이터 반영",
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3 py-1.5" style={{ borderBottom: "1px solid #1a1a1a" }}>
              <span className="text-[12px] font-black w-4 text-center shrink-0 mt-0.5" style={{ color: "#39ff8f" }}>{i + 1}</span>
              <p className="text-[12px]" style={{ color: "var(--text-secondary)" }}>{step}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[12px] leading-relaxed" style={{ color: "var(--text-faint)" }}>
          ※ 미국 → 한국 순서로 실행하는 이유: Gemini AI API 요청 한도(분당 요청 수) 때문입니다.
          동시 실행 시 60개 이상의 요청이 한꺼번에 몰려 503 오류가 발생할 수 있습니다.
        </p>
      </Card>

      {/* What this tool does */}
      <Card>
        <SectionTitle>이 툴이 하는 것</SectionTitle>
        <div className="grid grid-cols-2 gap-2">
          {[
            ["시장 체제 감지",   "미국(5센서)·한국(4센서) 가중 합산 → risk_on / neutral / risk_off / crisis 판별"],
            ["종목 스크리닝",    "미국(5팩터)·한국(4팩터) 복합 점수로 순위 산정. 등급 A~F + BUY/WATCH/HOLD 액션 부여"],
            ["AI 요약 생성",    "Gemini 2.5 Flash — 한국은 KOSPI 전문 프롬프트 사용. 목표주가(원화·달러) + 촉매·리스크"],
            ["섹터 분석",       "경기 사이클 단계 판단 + 섹터별 KOSPI/SPY 대비 상대강도"],
            ["포지션 계산기",   "고정 비율(Fixed Fraction)·켈리 공식으로 적정 매수 수량 자동 계산"],
            ["리스크 관리",     "VaR95·MDD 모니터링 + 체제별 손절선 제공"],
            ["페이퍼 포트폴리오", "BUY 추천 종목 가상 운용. 매수·매도·손익 추적으로 전략 검증"],
            ["실제 포트폴리오",  "보유 종목 등록·현재가 자동 조회·손익 계산. 실제 포지션 손절가 경보"],
          ].map(([title, desc]) => (
            <div key={title} className="rounded-xl p-3" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <p className="text-[12px] font-semibold text-white mb-0.5">{title}</p>
              <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>{desc}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[12px] leading-relaxed" style={{ color: "var(--text-faint)" }}>
          ※ 실제 매매 주문·자동 거래는 지원하지 않습니다. 모든 예측은 확률적 참고 자료이며 수익을 보장하지 않습니다.
        </p>
      </Card>

      {/* Daily routine */}
      <Card>
        <SectionTitle>매일 투자 의사결정 루틴</SectionTitle>
        <div className="space-y-2 mb-4">
          {[
            { n: "①", tab: "개요",          action: "마켓 게이트 확인 — STOP이면 오늘 매매 없음",                      href: "/" },
            { n: "②", tab: "시장 체제",     action: "레짐 확인 → 레짐별 권장 주식 비중으로 포트폴리오 조정",          href: "/regime" },
            { n: "③", tab: "종목 분석",     action: "BUY 종목 검토 → 클릭하여 AI 목표가·팩터·PER·PBR 상세 확인",     href: "/top-picks" },
            { n: "④", tab: "섹터 분석",     action: "경기 사이클 확인 → 강세 섹터 종목 우선 고려",                    href: "/sector" },
            { n: "⑤", tab: "투자 워크플로우", action: "6단계 시장 신호 확인 → 하단 체크리스트 10가지 통과 후 매수",    href: "/workflow" },
            { n: "⑥", tab: "포지션 계산기", action: "리스크 페이지에서 적정 매수 수량 수학적으로 확인",                href: "/risk" },
          ].map(({ n, tab, action, href }) => (
            <div key={n} className="flex items-start gap-3 rounded-xl p-3" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <span className="text-sm font-black shrink-0 w-5 text-center" style={{ color: "#39ff8f" }}>{n}</span>
              <div className="flex-1 min-w-0">
                <Link href={href} className="text-[12px] font-semibold text-white hover:underline">{tab}</Link>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>{action}</p>
              </div>
            </div>
          ))}
        </div>

        <SectionTitle>마켓 게이트 신호별 대응</SectionTitle>
        <div className="grid grid-cols-3 gap-2">
          {[
            { signal: "GO",      color: "#39ff8f", desc: "상위 종목 BUY 검토 → 워크플로우 5단계 통과 후 매수." },
            { signal: "CAUTION", color: "#facc15", desc: "신규 진입 시 포지션 50% 이하 축소. 손절선 1~2% 좁게." },
            { signal: "STOP",    color: "#ef4444", desc: "신규 진입 전면 보류. 기존 포지션 손절선 재검토." },
          ].map(({ signal, color, desc }) => (
            <div key={signal} className="rounded-xl p-3" style={{ background: "#222222", border: `1px solid ${color}33` }}>
              <Badge text={signal} color={color} />
              <p className="text-[12px] leading-relaxed mt-2" style={{ color: "var(--text-secondary)" }}>{desc}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Workflow 5 steps */}
      <Card>
        <SectionTitle>투자 워크플로우 6단계</SectionTitle>
        <div className="space-y-1">
          {STEPS.map((s) => (
            <div key={s.n} className="flex items-center gap-3 py-2" style={{ borderBottom: "1px solid #2e2e2e" }}>
              <span className="text-[12px] font-black w-5 text-center shrink-0" style={{ color: "#39ff8f" }}>{s.n}</span>
              <span className="text-[12px] font-semibold text-white w-28 shrink-0">{s.label}</span>
              <span className="text-[12px] flex-1" style={{ color: "var(--text-muted)" }}>{s.check}</span>
              <span className="text-[12px] font-bold px-1.5 py-0.5 rounded mr-2 shrink-0"
                style={{ background: `${AUTO_COLOR[s.auto]}18`, color: AUTO_COLOR[s.auto], border: `1px solid ${AUTO_COLOR[s.auto]}44` }}>
                {s.auto}
              </span>
              <Badge text={s.go} color="#39ff8f" />
            </div>
          ))}
        </div>
        <p className="mt-3 text-[12px]" style={{ color: "var(--text-faint)" }}>
          6개 신호 모두 초록(GO) → 하단 체크리스트에서 티커·손절가·수량 입력 후 매수 진행 · 하나라도 빨강(STOP) → 해당 조건 재검토
        </p>
      </Card>

      {/* Regime + factor weights */}
      <Card>
        <SectionTitle>시장 체제별 전략</SectionTitle>
        <div className="space-y-1 mb-5">
          {REGIME_ROWS.map((r) => (
            <div key={r.regime} className="flex items-center gap-3 py-2" style={{ borderBottom: "1px solid #2e2e2e" }}>
              <span className="text-[12px] font-semibold w-32 shrink-0" style={{ color: "#39ff8f" }}>{r.label}</span>
              <span className="text-[12px] flex-1" style={{ color: "var(--text-secondary)" }}>{r.meaning}</span>
              <span className="text-[12px] w-28 shrink-0 text-right" style={{ color: "var(--text-muted)" }}>{r.strategy}</span>
              <span className="text-[12px] font-bold w-12 text-right shrink-0" style={{ color: "#60a5fa" }}>{r.equity}</span>
              <span className="text-[12px] font-bold w-10 text-right shrink-0" style={{ color: "#ef4444" }}>{r.stop}</span>
            </div>
          ))}
        </div>
        <div className="flex gap-2 text-[12px]" style={{ color: "var(--text-faint)" }}>
          <span className="font-bold" style={{ color: "#60a5fa" }}>■</span> 권장 주식 비중
          <span className="ml-3 font-bold" style={{ color: "#ef4444" }}>■</span> 개별 종목 손절 기준
        </div>
      </Card>

      {/* Factor weights US vs KR */}
      <Card>
        <SectionTitle>종합 점수(Composite Score) 구조</SectionTitle>

        {/* US 6 factors */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className="text-[12px] font-bold mb-2" style={{ color: "#60a5fa" }}><FlagIcon market="US" size={13} />{" "}미국 (6팩터)</p>
            <div className="space-y-1">
              {[
                ["기술 (Technical)",    "25%", "RSI·MACD·볼린저밴드·이동평균 정렬"],
                ["펀더멘털 (Fundamental)", "20%", "PEG·EPS성장률·애널리스트 목표가 상승여력"],
                ["애널리스트 (Analyst)", "15%", "월가 컨센서스 목표가 상승여력"],
                ["상대강도 (RS vs SPY)", "15%", "최근 20일 SPY 대비 초과 수익률"],
                ["거래량 (Volume)",      "15%", "최근 5일 vs 20일 평균 거래량 Z-score"],
                ["기관 (Institutional)", "10%", "기관 보유 비율"],
              ].map(([f, w, tip]) => (
                <div key={f} className="flex items-center gap-2 text-[12px] py-1" style={{ borderBottom: "1px solid #1a1a1a" }}>
                  <span className="flex-1" style={{ color: "var(--text-secondary)" }}>{f}</span>
                  <span className="font-bold w-8 text-right shrink-0" style={{ color: "#60a5fa" }}>{w}</span>
                  <span className="w-44 text-right shrink-0" style={{ color: "#6e6e6e" }}>{tip}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[12px] font-bold mb-2" style={{ color: "#39ff8f" }}><FlagIcon market="KR" size={13} />{" "}한국 (4팩터)</p>
            <div className="space-y-1">
              {[
                ["기술 (Technical)",     "25%", "RSI·MACD·볼린저밴드·이동평균"],
                ["펀더멘털 (Fundamental)", "20%", "PER·PBR·ROE·PEG·EPS성장·부채"],
                ["상대강도 (RS vs KOSPI)", "15%", "최근 20일 KOSPI 대비 초과 수익률"],
                ["거래량 (Volume)",       "15%", "최근 5일 vs 20일 평균 거래량 Z-score"],
              ].map(([f, w, tip]) => (
                <div key={f} className="flex items-center gap-2 text-[12px] py-1" style={{ borderBottom: "1px solid #1a1a1a" }}>
                  <span className="flex-1" style={{ color: "var(--text-secondary)" }}>{f}</span>
                  <span className="font-bold w-8 text-right shrink-0" style={{ color: "#39ff8f" }}>{w}</span>
                  <span className="w-44 text-right shrink-0" style={{ color: "#6e6e6e" }}>{tip}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 기술적 가중 이유 설명 */}
        <div className="rounded-xl p-3 mb-4" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
          <p className="text-[12px] font-bold mb-1.5" style={{ color: "#facc15" }}>왜 기술적 지표 비중이 높은가?</p>
          <p className="text-[12px] leading-relaxed" style={{ color: "#a8a8a8" }}>
            AlphaDesk는 <span className="text-white font-semibold">탑다운(매크로 → 섹터 → 종목)</span> 구조로 작동합니다.
            체제 분석과 섹터 사이클에서 &quot;좋은 환경인가&quot;를 먼저 판단하고, 종합 점수는 그 환경 안에서 &quot;지금 살 타이밍인가&quot;를 고릅니다.
            이미 펀더멘털 필터(BUY 액션, Grade A/B)를 통과한 종목들 중에서 모멘텀·거래량·상대강도로 진입 타이밍을 선별하는 것이므로, 기술적 가중이 높은 게 이 구조에 맞습니다.
            Lynch도 실제 매수 타이밍은 차트를 참고했고, O&apos;Neil은 이를 원칙화했습니다.
          </p>
        </div>

        {/* 등급 기준 */}
        <div className="mt-2">
          <p className="text-[12px] font-bold mb-2" style={{ color: "var(--text-muted)" }}>등급 기준</p>
          <div className="grid grid-cols-5 gap-1">
            {[
              { grade: "A", score: "80+",   color: "#39ff8f" },
              { grade: "B", score: "70~79", color: "#86efac" },
              { grade: "C", score: "60~69", color: "#facc15" },
              { grade: "D", score: "50~59", color: "#f97316" },
              { grade: "F", score: "50미만", color: "#ef4444" },
            ].map(({ grade, score, color }) => (
              <div key={grade} className="rounded-xl p-2 text-center" style={{ background: `${color}11`, border: `1px solid ${color}33` }}>
                <p className="text-sm font-black" style={{ color }}>{grade}</p>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--text-faint)" }}>{score}점</p>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* AI 신뢰도 + 워크플로우 종목 우선순위 */}
      <Card>
        <SectionTitle>알아두면 유용한 해석법</SectionTitle>
        <div className="space-y-3">

          {/* AI 신뢰도 */}
          <div>
            <p className="text-[12px] font-bold text-white mb-1">AI 신뢰도(Confidence)란?</p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              Gemini AI가 자신의 분석에 스스로 매긴 확신 점수입니다 (0-100 정수).
              데이터가 충분하고 투자 논리가 일관되면 높게, 데이터가 불완전하거나 논리가 애매하면 낮게 냅니다.
              객관적 지표가 아닌 <span className="text-white">AI의 주관적 자기평가</span>입니다.
            </p>
            <div className="flex gap-2 mt-2">
              {[
                { range: "85+", desc: "근거에 확신 있음", color: "#39ff8f" },
                { range: "70~84", desc: "보통 수준", color: "#facc15" },
                { range: "~69", desc: "AI도 불확실한 상황", color: "#f97316" },
              ].map(({ range, desc, color }) => (
                <div key={range} className="flex-1 rounded-lg px-2.5 py-2 text-center" style={{ background: `${color}10`, border: `1px solid ${color}30` }}>
                  <p className="text-[12px] font-black" style={{ color }}>{range}</p>
                  <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>{desc}</p>
                </div>
              ))}
            </div>
            <p className="text-[12px] mt-1.5" style={{ color: "#6e6e6e" }}>※ AI 신뢰도는 참고용입니다. Gemini가 틀려도 책임은 없으므로 과신 금물.</p>
          </div>

          <div style={{ borderTop: "1px solid #2e2e2e", paddingTop: "1rem" }}>
            <p className="text-[12px] font-bold text-white mb-1">워크플로우 STEP 3 종목 우선순위 원리</p>
            <p className="text-[12px] leading-relaxed mb-2" style={{ color: "var(--text-muted)" }}>
              워크플로우가 추천하는 상위 종목 순서는 상위 종목 탭의 점수 순서와 다를 수 있습니다.
              STEP 3은 <span className="text-white">BUY + A/B등급</span> 필터 후, 그 안에서 <span className="text-white">현재 선행 섹터 종목을 먼저</span> 올립니다.
            </p>
            <div className="rounded-lg px-3 py-2.5 text-[12px]" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
              <p style={{ color: "#6e6e6e" }}>예) XLK(Technology)가 선행 섹터일 때</p>
              <p className="mt-1" style={{ color: "#a8a8a8" }}>
                전체 1위 CVS(Healthcare) 보다 4위 KLAC(Technology)를 먼저 추천 →
                <span className="text-white"> 지금 시장이 선호하는 섹터에서 타야 한다</span>는 전략적 판단
              </p>
            </div>
            <div className="rounded-lg px-3 py-2 mt-2" style={{ background: "#facc1508", border: "1px solid #facc1520" }}>
              <p className="text-[12px]" style={{ color: "#facc15" }}>⚠ 섹터 편중 주의</p>
              <p className="text-[12px] mt-0.5" style={{ color: "#a8a8a8" }}>
                선행 섹터가 하나일 때 상위 추천이 모두 같은 섹터일 수 있습니다. 플레이북 원칙대로 <span className="text-white">4-5종목 이내, 같은 섹터 최대 1-2종목</span>을 직접 판단해서 지키세요.
              </p>
            </div>
          </div>

        </div>
      </Card>

      {/* Tab reference */}
      <Card>
        <SectionTitle>전체 탭 한눈에 보기</SectionTitle>
        <div className="space-y-1">
          {GUIDE_SECTIONS.map((t) => (
            <div key={t.href} className="flex items-start gap-3 py-2" style={{ borderBottom: "1px solid #1a1a1a" }}>
              <span className="w-4 text-center text-base shrink-0" style={{ color: "#39ff8f" }}>{t.icon}</span>
              <Link href={t.href} className="text-[12px] font-semibold text-white hover:underline w-28 shrink-0">{t.label}</Link>
              <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>{t.desc}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* FAQ */}
      <Card>
        <SectionTitle>자주 묻는 질문</SectionTitle>
        <div className="space-y-3">
          {[
            {
              q: "분석 중 '503 서버 과부하' 오류가 나왔어요.",
              a: "Gemini AI API의 요청 한도 초과입니다. 자동 재시도 로직(최대 4회)이 있으므로 기다리면 됩니다. AlphaDesk_전체시작.bat으로 실행하면 미국 완료 후 한국이 시작되어 오류 확률이 크게 줄어듭니다.",
            },
            {
              q: "페이퍼 포트폴리오 편입가는 어떻게 정해지나요?",
              a: "분석 당일 종가(close) 기준입니다.",
            },
            {
              q: "AI 분석이 없는 종목이 있어요.",
              a: "AI 요약은 BUY 액션 종목에 대해서만 생성됩니다(한국 상위 15개, 미국 상위 50개). WATCH·HOLD 종목은 생성되지 않습니다.",
            },
            {
              q: "한국 종목에 PER·PBR 데이터가 없어요.",
              a: "yfinance가 해당 종목 정보를 가져오지 못한 경우입니다. 종합 점수는 데이터가 있는 팩터만으로 계산됩니다.",
            },
            {
              q: "GO 신호가 떠도 손실이 날 수 있나요?",
              a: "네. 모든 예측은 확률적 참고 자료입니다. 손절선 설정과 포지션 크기 관리를 항상 병행하세요.",
            },
            {
              q: "데이터가 없거나 '—' 표시가 뜨는 경우는?",
              a: "분석 파이프라인이 실행되지 않았거나 API 오류입니다. 해당 분석 스크립트를 실행하고 F5로 새로고침하세요.",
            },
          ].map(({ q, a }) => (
            <div key={q}>
              <p className="text-[12px] font-semibold text-white mb-1">Q. {q}</p>
              <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>{a}</p>
            </div>
          ))}
        </div>
      </Card>

      <p className="text-[12px] text-center pb-4" style={{ color: "#4a4a4a" }}>
        AlphaDesk는 투자 참고 도구입니다. 최종 투자 판단과 책임은 항상 본인에게 있습니다.
      </p>
    </div>
  );
}
