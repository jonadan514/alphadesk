"use client";

import Link from "next/link";

const GUIDE_SECTIONS = [
  { href: "/",           icon: "⊡", label: "개요",        desc: "이번 주 워치리스트 후보 수 요약. 접속 시작점." },
  { href: "/briefing",   icon: "📋", label: "주간 브리핑", desc: "매주 월요일 아침 자동 생성 — 지난주 지수 흐름·워치리스트 변동·관심도 흐름·다가오는 촉매·GPT 총평." },
  { href: "/sector",     icon: "⊞", label: "섹터 분석",   desc: "경기 사이클 단계와 지금 강한 업종 확인. 어느 분야 종목을 살지 방향을 잡는 탭." },
  { href: "/radar",      icon: "📡", label: "테마 레이더", desc: "미국 산업 테마 약 30개를 뉴스·실적·주가 세 축으로 매주 관찰. 종합 점수 없이, 정해진 조합에만 라벨을 붙임." },
  { href: "/watchlist",  icon: "🔖", label: "워치리스트",  desc: "재무 건전성 필터(Piotroski 등)를 통과한 후보를 순위 없이 리스트업(주간 갱신). 종목 클릭 시 재무 지표 + 뉴스 기반 네러티브 브리프 + 정성 체크리스트 + 메모까지 한 팝업에서." },
  { href: "/scorecard",  icon: "📈", label: "성적표",      desc: "과거 워치리스트 후보에 실제 주가를 대조한 사후 검증 — 지수 단순 보유 대비 필터가 값을 더했는지 확인." },
];

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
          <Badge text="GUIDE" color="#ffb020" />
        </div>
        <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          미국(S&amp;P 500) · 한국(KOSPI) 개인 투자자용 AI 주식 분석 대시보드
        </p>
        <Link
          href="/guide/detail"
          className="inline-flex items-center gap-1.5 mt-3 text-[12px] font-semibold rounded-xl px-3 py-1.5 transition-colors"
          style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
        >
          <span style={{ color: "#ffb020" }}>◉</span>
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
              step: "STEP 1", color: "#ffb020",
              title: "이번 주 후보가 몇 개인가? → 개요",
              body: "홈 화면에 이번 주 재무 필터를 통과한 워치리스트 후보 수가 뜹니다. 매수·매도 신호가 아니라 \"검토해볼 만한 후보 목록\"이라는 뜻입니다.",
            },
            {
              step: "STEP 2", color: "#facc15",
              title: "어떤 종목을 살까? → 워치리스트",
              body: "워치리스트 탭에는 재무 건전성 필터(Piotroski F-Score·ROE·부채비율·이자보상배율·현금흐름)를 통과한 후보가 순위 없이 나열됩니다 — 점수로 줄 세우지 않고, 통과한 종목 전부를 보여줍니다. 종목을 클릭하면 재무 지표와 함께 네러티브 브리프(시장이 왜 이 종목에 관심을 갖는지, 다가오는 촉매, 스토리가 깨지는 조건)가 표시돼요. 1~3년 보유를 전제로 한 도구이니 최종 종목 선택은 순위가 아니라 본인의 판단으로 하세요.",
            },
            {
              step: "STEP 3", color: "#6fb3b8",
              title: "정말 사도 되나? → 워치리스트 팝업에서 직접 판단",
              body: "워치리스트에서 종목을 클릭하면 재무 지표·네러티브 브리프와 함께 정성 체크리스트(스토리·촉매 점검)와 메모를 그 자리에서 남길 수 있습니다. 매수 여부·수량·타이밍은 이 도구가 판정해주지 않습니다 — 재무가 건전한 후보 중 무엇을 살지는 항상 본인의 판단입니다.",
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

        <div className="rounded-xl p-4" style={{ background: "#ffb02008", border: "1px solid #ffb02022" }}>
          <p className="text-[12px] font-bold" style={{ color: "#ffb020" }}>💡 가장 중요한 규칙 하나만 기억한다면</p>
          <p className="text-[13px] font-bold text-white mt-1">보유 이유가 사라졌는지 정기적으로 점검하고, 그렇다면 매도한다</p>
          <p className="text-[12px] mt-1" style={{ color: "var(--text-muted)" }}>
            AlphaDesk는 1~3년 펀더멘털 보유를 기본 전제로 합니다 — 단기 가격 변동에 따른 자동 손절은 없고,
            매수·매도 실행이나 보유 종목 추적 기능도 제공하지 않습니다. 재무 건전성 필터를 통과한 후보를
            정기적으로 다시 훑어보고, 애초에 보유 이유였던 스토리·촉매가 사라졌는지 본인이 직접 점검하세요.
          </p>
        </div>
      </Card>

      {/* 데이터 업데이트 */}
      <Card>
        <SectionTitle>데이터 업데이트 방식</SectionTitle>
        <div className="space-y-2 mb-4">
          {[
            { label: "워치리스트 스크리닝 (주 1회)", color: "#6fb3b8", desc: "매주 일요일 밤 자동 실행 — 재무 건전성 필터(트랩 필터) 통과 종목 전부를 순위 없이 리스트업", tag: "자동" },
            { label: "네러티브 브리프 (주 1회)", color: "#f87171", desc: "워치리스트 스크리닝 직후 후보·내 워치리스트 종목별 최근 1주 뉴스를 수집해 GPT가 장기 스토리·촉매·리스크·시장 단기 관심도(HOT/WARM/COLD)를 생성", tag: "자동" },
            { label: "시장 분석 (주 1회)", color: "#ffb020", desc: "GitHub Actions가 매주 월요일 자동 실행 — 섹터 분석 갱신", tag: "자동" },
            { label: "텔레그램 요약 (자동)", color: "#6fb3b8", desc: "주간 시장 분석 완료 후 워치리스트 교차 히트·관심도 상승을 폰으로 발송", tag: "자동" },
            { label: "정성 체크리스트", color: "#a39c88", desc: "종목별 체크리스트·메모는 내가 직접 입력", tag: "수동" },
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
            "사이드바 하단 색상 점 — 초록(7일 이내 업데이트) · 노랑(8~9일 전) · 빨강(오래됨) — 주 1회 실행 체제라 며칠 지난 건 정상입니다",
            "빨강이면 GitHub Actions 실행 결과를 확인하세요",
            "수동 재실행: GitHub → Actions → Weekly Market Analysis → Run workflow",
            "워치리스트 재스크리닝: GitHub → Actions → Weekly Watchlist Screen → Run workflow",
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3 py-1.5" style={{ borderBottom: "1px solid #262112" }}>
              <span className="text-[12px] font-black w-4 text-center shrink-0 mt-0.5" style={{ color: "#ffb020" }}>{i + 1}</span>
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
            ["워치리스트",      "재무 건전성 필터(Piotroski·ROE·부채비율·이자보상배율·현금흐름)를 통과한 종목을 주 1회, 순위 없이 리스트업"],
            ["네러티브 브리프",  "후보 종목별 최근 뉴스를 GPT가 요약 — 장기 투자 스토리·촉매·리스크·시장 단기 관심도(HOT/WARM/COLD)"],
            ["섹터 분석",       "경기 사이클 단계 판단 + 섹터별 KOSPI/SPY 대비 상대강도"],
            ["테마 레이더",     "미국 산업 테마 약 30개를 뉴스·실적·주가 세 축으로 주 1회 관찰, 정해진 조합에만 라벨 부여(미국만)"],
            ["텔레그램 알림",   "주간 분석 후 워치리스트 교차 히트·관심도 상승 신호를 요약해 폰으로 발송"],
            ["성적표",          "과거 후보에 실제 주가를 대조한 사후 검증 — 지수 단순 보유 대비 필터가 값을 더했는지"],
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

      {/* Weekly routine */}
      <Card>
        <SectionTitle>주간 투자 의사결정 루틴</SectionTitle>
        <div className="space-y-2 mb-4">
          {[
            { n: "①", tab: "텔레그램 요약", action: "주간 분석 완료 후 요약 메시지 확인 — 별다른 신호 없으면 이번 주는 끝", href: "/" },
            { n: "②", tab: "개요",          action: "신호가 있으면 접속 — 이번 주 후보 수 + 테마 레이더 라벨 요약 확인", href: "/" },
            { n: "③", tab: "테마 레이더",   action: "라벨 붙은 테마가 있으면 훑어보기 — 특히 \"Quiet Strength\"는 뉴스만 봐서는 못 찾는 신호", href: "/radar" },
            { n: "④", tab: "워치리스트",    action: "관심도 상승 배너 확인 → 눈에 띄는 후보 클릭해 네러티브 브리프 읽기 + 정성 체크 + 메모", href: "/watchlist" },
          ].map(({ n, tab, action, href }) => (
            <div key={n} className="flex items-start gap-3 rounded-xl p-3" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <span className="text-sm font-black shrink-0 w-5 text-center" style={{ color: "#ffb020" }}>{n}</span>
              <div className="flex-1 min-w-0">
                <Link href={href} className="text-[12px] font-semibold text-white hover:underline">{tab}</Link>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>{action}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Trap filter thresholds */}
      <Card>
        <SectionTitle>재무 건전성 필터(트랩 필터) 구조</SectionTitle>
        <p className="text-[12px] mb-3 leading-relaxed" style={{ color: "var(--text-muted)" }}>
          점수를 매겨 순위를 매기는 게 아니라, 아래 항목 중 하나라도 걸리면 <span className="text-white font-semibold">탈락</span>하는
          방식입니다. 통과한 종목은 전부 워치리스트 후보가 되고(순위 없음), 그 안에서 어떤 종목을 살지는 본인이 판단합니다.
        </p>
        <div className="space-y-1">
          {[
            ["Piotroski F-Score", "6점 미만이면 탈락 (9개 항목 중 수익성·레버리지·운영효율 채점)"],
            ["이자보상배율(EBIT/이자비용)", "3배 미만이면 탈락 — 이자는 내지만 안전마진이 부족한 상태도 제외"],
            ["부채비율(총부채/자기자본)", "150% 초과면 탈락 (금융업 제외)"],
            ["영업현금흐름", "최근 2년 연속 마이너스면 탈락"],
            ["매출 + 순이익", "3년 연속 동시 감소면 탈락 (매출만 2년 연속 감소도 별도 감점 사유)"],
            ["ROE", "12% 미만이면 탈락"],
          ].map(([f, tip]) => (
            <div key={f} className="flex items-center gap-2 text-[12px] py-1.5" style={{ borderBottom: "1px solid #262112" }}>
              <span className="w-48 shrink-0 font-semibold" style={{ color: "var(--text-secondary)" }}>{f}</span>
              <span className="flex-1" style={{ color: "#726b58" }}>{tip}</span>
            </div>
          ))}
        </div>
        <div className="rounded-xl p-3 mt-4" style={{ background: "#0e0d08", border: "1px solid #262112" }}>
          <p className="text-[12px] font-bold mb-1.5" style={{ color: "#facc15" }}>왜 모멘텀·기술적 지표는 안 보나?</p>
          <p className="text-[12px] leading-relaxed" style={{ color: "#a39c88" }}>
            예전 버전은 기술적 지표·상대강도·거래량으로 &quot;지금 살 타이밍인가&quot;까지 점수화했고, 한때는
            시장 체제·마켓 게이트로 진입 타이밍까지 판정했습니다. 1~3년 보유를 전제로 하면 그 시점의 단기
            타이밍은 큰 의미가 없다고 판단해 모두 제거했습니다. 지금은 재무가 건전한 회사인지만 걸러내고,
            언제·얼마나 살지는 전적으로 본인이 판단합니다.
          </p>
        </div>
      </Card>

      {/* AI 신뢰도 + 워크플로우 종목 우선순위 */}
      <Card>
        <SectionTitle>알아두면 유용한 해석법</SectionTitle>
        <div className="space-y-3">

          {/* 시장 단기 관심도 */}
          <div>
            <p className="text-[12px] font-bold text-white mb-1">네러티브 브리프의 &quot;시장 단기 관심도&quot;란?</p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              최근 1주일 뉴스량을 기준으로 GPT가 매기는 HOT/WARM/COLD 표시입니다.
              <span className="text-white"> 장기 투자 판단의 핵심 지표가 아니라 보조 정보</span>일 뿐입니다 —
              관심 밖(COLD)이어도 장기 스토리(story)는 탄탄할 수 있고, 반대로 HOT이라고 재무가 좋은 것도 아닙니다.
            </p>
            <div className="flex gap-2 mt-2">
              {[
                { range: "🔥 HOT", desc: "뉴스 많음, 인기 테마", color: "#f87171" },
                { range: "🌤 WARM", desc: "꾸준한 관심", color: "#facc15" },
                { range: "❄️ COLD", desc: "뉴스 적음, 관심 밖", color: "#6fb3b8" },
              ].map(({ range, desc, color }) => (
                <div key={range} className="flex-1 rounded-lg px-2.5 py-2 text-center" style={{ background: `${color}10`, border: `1px solid ${color}30` }}>
                  <p className="text-[12px] font-black" style={{ color }}>{range}</p>
                  <p className="text-[12px] mt-0.5" style={{ color: "#726b58" }}>{desc}</p>
                </div>
              ))}
            </div>
            <p className="text-[12px] mt-1.5" style={{ color: "#726b58" }}>※ 판단의 중심은 항상 story(투자 스토리)·catalysts(촉매)·risks(리스크)입니다.</p>
          </div>

          <div style={{ borderTop: "1px solid #262112", paddingTop: "1rem" }}>
            <p className="text-[12px] font-bold text-white mb-1">워치리스트 후보에는 왜 순위가 없나?</p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              예전 버전은 재무 필터 통과 종목을 다시 모멘텀·품질 점수로 줄 세워 상위 50개만 보여줬습니다.
              하지만 1~3년 보유가 전제라면 스크리닝 시점의 순위가 실제 투자 성과와 크게 상관없다고 판단해 랭킹 자체를 없앴습니다.
              지금은 재무 필터를 통과한 종목 <span className="text-white">전부</span>가 후보이고, 그 안에서 무엇을 살지는
              섹터 분산·네러티브·본인의 확신을 기준으로 직접 고르는 게 맞는 방향이라고 봤습니다.
            </p>
          </div>

        </div>
      </Card>

      {/* Tab reference */}
      <Card>
        <SectionTitle>전체 탭 한눈에 보기</SectionTitle>
        <div className="space-y-1">
          {GUIDE_SECTIONS.map((t) => (
            <div key={t.href} className="flex items-start gap-3 py-2" style={{ borderBottom: "1px solid #262112" }}>
              <span className="w-4 text-center text-base shrink-0" style={{ color: "#ffb020" }}>{t.icon}</span>
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
              q: "네러티브 브리프가 없는 종목이 있어요.",
              a: "내 워치리스트 종목과 이번 주 후보는 모두 대상이지만, 후보 수가 많으면 오래된(또는 아직 없는) 종목부터 순서대로 매주 나눠서 갱신됩니다(회차당 최대 400종목). 며칠~몇 주 걸릴 수 있으니 조금 기다리거나 GitHub → Actions에서 Weekly Watchlist Screen을 수동 실행하세요.",
            },
            {
              q: "워치리스트 후보는 어떻게 뽑히나요?",
              a: "주 1회 자동 스크리닝 — 함정 필터(Piotroski≥6, ROE≥12%, 이자보상배율≥3, 부채비율≤150%, 영업현금흐름 2년 연속 마이너스 아님, 매출+순이익 3년 연속 감소 아님)를 통과한 종목 전부가 후보입니다. 더 이상 점수로 순위를 매겨 상위 N개만 자르지 않습니다. 한국은 현재 KOSPI 대형주 기준이라 후보가 더 적을 수 있어요.",
            },
            {
              q: "네러티브 브리프가 안 뜨는 종목이 있어요.",
              a: "브리프는 주간 워치리스트 스크리닝 직후 파이프라인이 생성합니다. 이번 주에 새로 후보에 오른 종목은 다음 주간 스크리닝 후에 표시돼요. '최근 뉴스 없음'으로 뜨는 건 정상 — 시장 관심 밖이라는 그 자체가 신호입니다.",
            },
            {
              q: "부채비율·이자보상배율이 숫자 대신 '무차입'·'자본잠식'으로 떠요.",
              a: "숫자가 없는 게 아니라 그 자체가 의미 있는 상태입니다. '무차입'은 이자비용이 없어 계산이 불필요한 좋은 상태, '자본잠식(음수 자본)'은 자기자본이 마이너스라 원인을 직접 확인해야 하는 주의 상태입니다. '데이터 없음'만 진짜 결측치입니다.",
            },
            {
              q: "재무 필터를 통과했는데도 손실이 날 수 있나요?",
              a: "네. 필터는 재무가 명백히 부실한 종목을 걸러낼 뿐 매수·매도 신호가 아닙니다. 통과 종목이라도 주가가 하락할 수 있고, 이 도구는 손절선·포지션 크기를 계산해주지 않습니다.",
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

      <p className="text-[12px] text-center pb-4" style={{ color: "#423e33" }}>
        AlphaDesk는 투자 참고 도구입니다. 최종 투자 판단과 책임은 항상 본인에게 있습니다.
      </p>
    </div>
  );
}
