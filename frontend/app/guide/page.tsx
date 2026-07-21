"use client";

import Link from "next/link";
import FlagIcon from "@/src/components/FlagIcon";

const GUIDE_SECTIONS = [
  { href: "/",          icon: "⊡", label: "개요",        desc: "마켓 게이트·체제·상위 픽·지수 예측을 한 화면 요약. 오늘 시장 상태를 5초에 파악하는 시작점." },
  { href: "/briefing",  icon: "📋", label: "주간 브리핑", desc: "매주 월요일 아침 자동 생성 — 지난주 시장 궤적·워치리스트 변동·관심도 흐름·다가오는 촉매·GPT 총평." },
  { href: "/regime",    icon: "▦", label: "시장 체제",   desc: "지금 시장이 강세/약세/위기 중 어느 단계인지 판단. 체제별 권장 주식 비중·손절선 + 글로벌 매크로 스냅샷." },
  { href: "/sector",    icon: "⊞", label: "섹터 분석",   desc: "경기 사이클 단계와 지금 강한 업종 확인. 어느 분야 종목을 살지 방향을 잡는 탭." },
  { href: "/top-picks", icon: "★", label: "종목 분석",   desc: "매일 팩터 점수로 선별되는 발굴 레이더. 종목 클릭 시 AI 투자 근거·목표가·리스크 확인. 내 워치리스트 종목은 🔖 배지." },
  { href: "/watchlist", icon: "🔖", label: "워치리스트",  desc: "함정 필터 + 시장 적합 점수 상위 50 후보(주간 갱신). 종목 클릭 시 재무 지표 + 네러티브 브리프 + 정성 체크리스트 + 메모까지 한 팝업에서." },
  { href: "/workflow",  icon: "▶", label: "매수 체크",   desc: "주문 직전 최종 관문. 티커 입력 시 13개 조건 중 11개를 실시간 자동 판정 + 적정 수량 계산." },
  { href: "/portfolio", icon: "◈", label: "포트폴리오",  desc: "실제 매수/매도 기록 + 현재가·평가손익 실시간 표시. 손절선 접근/도달 시 자동 경고." },
  { href: "/risk",      icon: "⛨", label: "리스크",      desc: "시스템 시뮬레이션 포트폴리오의 위험 분석 — VaR·상관관계·종목별 낙폭." },
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
              title: "어떤 종목을 살까? → 워치리스트 + 종목 분석",
              body: "워치리스트 탭에는 재무 함정 필터와 시장 적합 점수를 통과한 상위 50개 후보가 있습니다. 종목을 클릭하면 재무 지표와 함께 네러티브 브리프(시장이 왜 이 종목에 관심을 갖는지, 다가오는 촉매, 스토리가 깨지는 조건)가 표시돼요. 종목 분석 탭은 매일 갱신되는 발굴 레이더 — 여기서 눈에 띈 종목도 워치리스트에서 검증하세요. 두 탭에 동시에 뜨는 종목(🔖워치 + 오늘픽)이 가장 강한 신호입니다.",
            },
            {
              step: "STEP 3", color: "#60a5fa",
              title: "정말 사도 되나? 얼마나 살까? → 워치리스트 팝업 + 매수 체크",
              body: "워치리스트에서 종목을 클릭하면 정성 체크리스트(스토리·촉매 점검)와 메모를 그 자리에서 남길 수 있습니다. 그다음 매수 체크 탭에 티커를 입력하면 13개 조건(게이트·체제·워치리스트 포함 여부·등급·점수 등)을 자동 판정하고 적정 매수 수량까지 계산해줍니다. 모든 항목이 초록이 되면 매수합니다.",
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
          <p className="text-[13px] font-bold text-white mt-1">체제별 손절선(강세 -10% ~ 위기 -3%)에 도달하면 이유 불문 즉시 매도</p>
          <p className="text-[12px] mt-1" style={{ color: "var(--text-muted)" }}>
            아무리 좋은 종목도 손절선 없이 보유하면 큰 손실로 이어집니다. 손절은 틀린 게 아니라 자산을 지키는 것입니다.
            포트폴리오 탭에 거래를 기록해두면 보유 종목이 손절선에 접근할 때 자동으로 경고해줘요.
          </p>
        </div>
      </Card>

      {/* 데이터 업데이트 */}
      <Card>
        <SectionTitle>데이터 업데이트 방식</SectionTitle>
        <div className="space-y-2 mb-4">
          {[
            { label: "일간 분석 (자동)",    color: "#39ff8f", desc: "GitHub Actions가 평일 매일 자동 실행 — 미국(장 마감 후 07:00 KST) · 한국(장 마감 후 16:30 KST)", tag: "자동" },
            { label: "네러티브 브리프 (자동)", color: "#f87171", desc: "일간 분석과 함께 워치리스트 종목별 최근 1주 뉴스를 수집해 GPT가 스토리·촉매·관심도(HOT/WARM/COLD)를 생성", tag: "자동" },
            { label: "워치리스트 (주 1회)", color: "#60a5fa", desc: "매주 월요일 자동 스크리닝 — 함정 필터 통과 후 시장 적합 점수(품질·모멘텀·체제) 상위 50개 선발", tag: "자동" },
            { label: "텔레그램 요약 (자동)", color: "#a78bfa", desc: "일간 분석 완료 후 게이트 상태·손절 경고·워치리스트 교차 히트·관심도 상승을 폰으로 발송", tag: "자동" },
            { label: "포트폴리오·정성 체크", color: "#a8a8a8", desc: "매수/매도 기록 및 종목별 체크리스트·메모는 내가 직접 입력", tag: "수동" },
          ].map(({ label, color, desc, tag }) => (
            <div key={label} className="flex items-start gap-3 rounded-xl p-3" style={{ background: "var(--bg-inset)", border: `1px solid ${color}33` }}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[12px] font-bold" style={{ color }}>{label}</span>
                  <Badge text={tag} color={color} />
                </div>
                <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>{desc}</p>
              </div>
            </div>
          ))}
        </div>

        <SectionTitle>데이터 신선도 확인</SectionTitle>
        <div className="space-y-1">
          {[
            "사이드바 하단 색상 점 — 초록(오늘 업데이트) · 노랑(어제) · 주황/빨강(오래됨)",
            "주황/빨강이면 GitHub Actions 실행 결과를 확인하세요",
            "수동 재실행: GitHub → Actions → Daily Analysis → Run workflow",
            "워치리스트 재스크리닝: GitHub → Actions → Weekly Watchlist Screen → Run workflow",
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3 py-1.5" style={{ borderBottom: "1px solid #1a1a1a" }}>
              <span className="text-[12px] font-black w-4 text-center shrink-0 mt-0.5" style={{ color: "#39ff8f" }}>{i + 1}</span>
              <p className="text-[12px]" style={{ color: "var(--text-secondary)" }}>{step}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* What this tool does */}
      <Card>
        <SectionTitle>이 툴이 하는 것</SectionTitle>
        <div className="grid grid-cols-2 gap-2">
          {[
            ["시장 체제 감지",   "미국(5센서)·한국(5센서) 가중 합산 → risk_on / neutral / risk_off / crisis 판별"],
            ["종목 스크리닝",    "미국(6팩터)·한국(4팩터) 복합 점수로 매일 순위 산정. 등급 A~F + BUY/WATCH/HOLD 액션"],
            ["워치리스트",      "함정 필터(Piotroski·ROE·부채 등) + 시장 적합 점수로 시장별 상위 50 후보를 주 1회 선발"],
            ["네러티브 브리프",  "종목별 최근 뉴스를 GPT가 요약 — 투자 스토리·촉매·리스크·시장 관심도(HOT/WARM/COLD)"],
            ["AI 요약 생성",    "GPT-4o — 투자 thesis · 상승 촉매 · 하락 리스크를 종목별로 자동 생성"],
            ["섹터 분석",       "경기 사이클 단계 판단 + 섹터별 KOSPI/SPY 대비 상대강도"],
            ["손절선 모니터",   "포트폴리오 보유 종목이 체제별 손절선에 접근·도달하면 자동 경고"],
            ["텔레그램 알림",   "매일 분석 후 행동이 필요한 신호만 요약해 폰으로 발송"],
            ["포지션 사이징",   "고정 비율·켈리 검증으로 적정 매수 수량 자동 계산 (매수 체크 탭)"],
            ["리스크 관리",     "VaR95·상관관계·낙폭 분석 (시스템 시뮬레이션 포트폴리오 기준)"],
            ["포트폴리오",      "실거래 기록 + 현재가·평가손익 실시간 표시, 벤치마크 대비 성과 추적"],
            ["정성 체크리스트", "워치리스트 팝업에 내장된 종목별 스토리·촉매 체크 + 메모"],
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
            { n: "①", tab: "텔레그램 요약", action: "아침 요약 메시지 확인 — 게이트 STOP이거나 별다른 신호 없으면 오늘은 끝", href: "/" },
            { n: "②", tab: "개요",          action: "신호가 있으면 접속 — 게이트·체제·지수 예측 확인",                  href: "/" },
            { n: "③", tab: "워치리스트",    action: "관심도 상승·오늘픽 배지 확인 → 눈에 띄면 클릭해 네러티브 브리프 읽기 + 정성 체크 + 메모", href: "/watchlist" },
            { n: "④", tab: "매수 체크",     action: "티커 입력 → 13개 조건 자동 판정 + 적정 수량 계산 → 전부 초록이면 매수", href: "/workflow" },
            { n: "⑤", tab: "포트폴리오",    action: "매수했으면 거래 기록 — 이후 손익·손절선 경고가 자동으로 표시됨",      href: "/portfolio" },
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
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
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
                ["기술 (Technical)",     "35%", "RSI·MACD·볼린저밴드·이동평균"],
                ["상대강도 (RS vs KOSPI)", "30%", "최근 20일 KOSPI 대비 초과 수익률"],
                ["펀더멘털 (Fundamental)", "20%", "PER·PBR·ROE·PEG·EPS성장·부채"],
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
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-1">
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
              GPT-4o가 자신의 분석에 스스로 매긴 확신 점수입니다 (0-100 정수).
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
            <p className="text-[12px] mt-1.5" style={{ color: "#6e6e6e" }}>※ AI 신뢰도는 참고용입니다. GPT-4o가 틀려도 책임은 없으므로 과신 금물.</p>
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
              q: "AI 분석이 없는 종목이 있어요.",
              a: "AI 요약은 BUY 액션 종목에 대해서만 생성됩니다(한국 상위 15개, 미국 상위 50개). WATCH·HOLD 종목은 생성되지 않습니다. 일간 분석 실행 후 업데이트됩니다.",
            },
            {
              q: "워치리스트 후보는 어떻게 뽑히나요?",
              a: "주 1회 자동 스크리닝 — ① 함정 필터(Piotroski≥5, ROE≥8%, 이자보상배율≥1, 부채비율≤200%, 현금흐름·매출 감소 없음)로 걸러낸 뒤 ② 시장 적합 점수(품질 40 + 모멘텀 35 + 체제 정합 25)로 시장별 상위 50개만 선발합니다. 한국은 현재 KOSPI 대형주 기준이라 후보가 더 적을 수 있어요.",
            },
            {
              q: "네러티브 브리프가 안 뜨는 종목이 있어요.",
              a: "브리프는 일간 파이프라인이 매일 생성합니다. 이번 주에 새로 후보에 오른 종목은 다음 일간 분석 후에 표시돼요. '최근 뉴스 없음'으로 뜨는 건 정상 — 시장 관심 밖이라는 그 자체가 신호입니다.",
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
