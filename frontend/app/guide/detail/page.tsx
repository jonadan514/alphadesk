"use client";

import { useState } from "react";

interface Section {
  id: string;
  icon: string;
  title: string;
  subtitle: string;
  content: React.ReactNode;
}

function Accordion({ sections }: { sections: Section[] }) {
  const [open, setOpen] = useState<string | null>(sections[0]?.id ?? null);
  return (
    <div className="space-y-2">
      {sections.map((s) => {
        const isOpen = open === s.id;
        return (
          <div key={s.id} className="bg-card rounded-xl overflow-hidden">
            <button
              className="w-full flex items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-white/[0.02]"
              onClick={() => setOpen(isOpen ? null : s.id)}
            >
              <span className="text-lg w-6 text-center shrink-0" style={{ color: "#39ff8f" }}>{s.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-white">{s.title}</p>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>{s.subtitle}</p>
              </div>
              <span className="text-[13px] shrink-0 transition-transform duration-200" style={{
                color: "#39ff8f",
                transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
                display: "inline-block",
              }}>▼</span>
            </button>
            {isOpen && (
              <div className="px-5 pb-5 pt-1 border-t" style={{ borderColor: "var(--border)" }}>
                {s.content}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-[12px] leading-relaxed mb-2" style={{ color: "var(--text-secondary)" }}>{children}</p>;
}
function H({ children }: { children: React.ReactNode }) {
  return <p className="text-[12px] font-bold text-white mt-4 mb-1.5">{children}</p>;
}
function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl px-4 py-3 mt-3 text-[12px] leading-relaxed" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
      {children}
    </div>
  );
}
function Table({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="rounded-xl overflow-hidden mt-3" style={{ border: "1px solid var(--border)" }}>
      <table className="w-full text-[13px]">
        <thead>
          <tr style={{ background: "var(--bg-inset)", borderBottom: "1px solid var(--border)" }}>
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-left text-[12px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: i < rows.length - 1 ? "1px solid var(--border-dim)" : "none" }}>
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2.5 text-[12px]" style={{ color: j === 0 ? "var(--text-primary)" : "var(--text-secondary)" }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Highlight({ children }: { children: React.ReactNode }) {
  return <span className="font-semibold" style={{ color: "#39ff8f" }}>{children}</span>;
}
function Warn({ children }: { children: React.ReactNode }) {
  return <span className="font-semibold" style={{ color: "#facc15" }}>{children}</span>;
}
function Danger({ children }: { children: React.ReactNode }) {
  return <span className="font-semibold" style={{ color: "#ef4444" }}>{children}</span>;
}

const SECTIONS: Section[] = [
  {
    id: "regime",
    icon: "▦",
    title: "시장 체제(Regime)란 무엇인가",
    subtitle: "왜 모든 판단이 체제에서 시작하는가",
    content: (
      <>
        <P>
          주식시장은 항상 같은 방식으로 움직이지 않습니다. 어떤 시기에는 거의 모든 종목이 오르고, 어떤 시기에는 좋은 종목도 같이 내립니다.
          이 툴은 그 차이를 먼저 판단하기 위해 <Highlight>시장 체제</Highlight>를 분류합니다.
        </P>
        <P>
          체제가 건강해야 좋은 종목도 오릅니다. 반대로 아무리 좋은 종목도 위기 국면에서는 버티기 어렵습니다.
          <Highlight>체제 판단은 매수 여부를 결정하는 첫 번째 필터</Highlight>입니다.
        </P>
        <H>4가지 체제 구분</H>
        <Table
          headers={["체제", "시장 상황", "권장 주식 비중", "손절 기준"]}
          rows={[
            ["risk_on",  "상승 추세, 변동성 낮음",   "70~80%", "-10%"],
            ["neutral",  "방향 불명확, 혼재 신호",   "50~60%", "-8%"],
            ["risk_off", "하락 압력, 변동성 상승",   "30~40%", "-5%"],
            ["crisis",   "시스템 리스크, 급락",      "10~20%", "-3%"],
          ]}
        />
        <H>미국 체제 센서 (5개)</H>
        <Table
          headers={["센서", "측정 내용", "가중치"]}
          rows={[
            ["VIX",         "변동성 공포 지수. 20 이하 = 안정",          "30%"],
            ["TREND",       "S&P 500 vs 200일 이동평균선",               "25%"],
            ["BREADTH",     "52주 신고가/신저가 비율",                    "18%"],
            ["CREDIT",      "회사채-국채 금리 스프레드",                  "15%"],
            ["YIELD CURVE", "10년물 - 2년물 금리차",                     "12%"],
          ]}
        />
        <H>한국 체제 센서 (5개)</H>
        <Table
          headers={["센서", "측정 내용", "가중치"]}
          rows={[
            ["TREND",      "KOSPI vs SMA50·SMA200",                     "30%"],
            ["VOLATILITY", "60일 실현 변동성 (VIX 대용)",               "20%"],
            ["MOMENTUM",   "60일 수익률 (중기 방향)",                    "20%"],
            ["BREADTH",    "250일 수익률 (장기 시장 폭)",               "15%"],
            ["USD/KRW",    "원/달러 환율 20일 추세 — 원화 약세 = 외국인 이탈 위험", "15%"],
          ]}
        />
        <Note>
          💡 한국 시장은 미국처럼 VIX나 신용 스프레드를 실시간 활용하기 어려워 KOSPI 가격 + 환율 기반 5개 센서로 구성됩니다.
          미국 매크로(VIX·금리)는 시장 체제 탭의 &quot;글로벌 매크로 스냅샷&quot;에서 함께 확인하세요.
        </Note>
      </>
    ),
  },
  {
    id: "screening",
    icon: "★",
    title: "팩터 스크리닝 — 복합 점수 계산",
    subtitle: "미국 6팩터 · 한국 4팩터로 종목을 선별하는 방법",
    content: (
      <>
        <P>
          스크리닝은 전 종목을 여러 관점에서 평가해 <Highlight>0~100점짜리 복합 점수</Highlight>를 만들고 순위를 매기는 과정입니다.
        </P>
        <H>미국 6팩터</H>
        <Table
          headers={["팩터", "측정 내용", "가중치"]}
          rows={[
            ["기술 (Technical)",      "RSI, MACD, SMA50/200 배열, 골든크로스",          "25%"],
            ["펀더멘털 (Fundamental)", "EPS 성장·PEG·ROE",                              "20%"],
            ["애널리스트 (Analyst)",   "목표주가 상승여력, BUY 의견 비율",               "15%"],
            ["상대강도 (RS)",          "SPY 대비 초과 수익률",                           "15%"],
            ["거래량 (Volume)",        "20일 평균 대비 최근 거래량 비율",                "15%"],
            ["기관 (Institutional)",   "기관 보유 비율·스마트머니 흐름",                 "10%"],
          ]}
        />
        <H>한국 4팩터</H>
        <Table
          headers={["팩터", "측정 내용", "가중치"]}
          rows={[
            ["기술 (Technical)",      "RSI, MACD, SMA50/200 배열",                      "35%"],
            ["펀더멘털 (Fundamental)", "PER, PBR, ROE, 이익성장률, 부채비율",           "20%"],
            ["상대강도 (RS)",          "KOSPI 대비 20일 수익률 차이",                    "30%"],
            ["거래량 (Volume)",        "20일 평균 대비 최근 거래량 비율",                "15%"],
          ]}
        />
        <H>Action 값 해석</H>
        <P>
          <Highlight>BUY</Highlight>: 현재 체제에서 진입 권고 (risk_on·neutral 시 70점 이상)<br />
          <Warn>WATCH</Warn>: 조건 충족 시 진입, 아직은 관망 (55~69점)<br />
          <Danger>HOLD</Danger>: 신규 진입 보류 (55점 미만)
        </P>
        <Note>
          💡 복합 점수가 높아도 시장 체제가 risk_off면 BUY로 분류되지 않을 수 있습니다. 체제와 스크리닝을 항상 같이 보세요.
        </Note>
      </>
    ),
  },
  {
    id: "ai",
    icon: "◎",
    title: "AI 분석 — GPT 요약 읽는 법",
    subtitle: "종목 분석 팝업의 AI 요약과 워치리스트의 네러티브 브리프",
    content: (
      <>
        <P>
          GPT-4o mini가 스크리닝 통과 종목에 대해 자동으로 작성한 분석 요약입니다.
          종목 분석 탭에서 종목을 클릭하면 팝업에 표시됩니다.
        </P>
        <H>AI 요약 vs 네러티브 브리프 — 뭐가 다른가</H>
        <Table
          headers={["구분", "AI 요약 (종목 분석)", "네러티브 브리프 (워치리스트)"]}
          rows={[
            ["재료",   "팩터 점수·재무 데이터",       "최근 1주일 실제 뉴스 헤드라인"],
            ["질문",   "숫자로 볼 때 살 만한가?",      "시장이 지금 무슨 스토리를 믿는가?"],
            ["산출물", "thesis·촉매·리스크·목표가",    "스토리·촉매·관심도(HOT/WARM/COLD)"],
          ]}
        />
        <H>미국 AI 분석</H>
        <Table
          headers={["항목", "내용"]}
          rows={[
            ["투자 테제 (Thesis)", "이 종목을 매수해야 하는 핵심 논리 (한국어 2~3문장)"],
            ["상승 촉매 (Catalysts)", "주가를 올릴 이벤트·요인 3개"],
            ["하락 리스크 (Bear Cases)", "thesis가 틀렸을 때 하락할 이유 2개"],
            ["목표주가 (Target Price)", "달러 기준 6~12개월 목표가"],
            ["AI 신뢰도 (Confidence)", "0~100점. 데이터가 충분할수록 높음"],
          ]}
        />
        <H>한국 AI 분석 (KOSPI 전문 프롬프트)</H>
        <Table
          headers={["항목", "내용"]}
          rows={[
            ["시장 컨텍스트", "KOSPI 체제·20일 모멘텀·경기 사이클·강세 섹터 정보를 AI에게 제공"],
            ["투자 테제", "한국 시장 특성(외국인 수급·환율·밸류에이션) 반영 (한국어 2~3문장)"],
            ["상승 촉매", "구체적 수치·일정 포함 3개"],
            ["하락 리스크", "환율·외국인 이탈·정치 리스크 등 한국 특유 리스크 포함 2개"],
            ["AI 목표주가", "원화(₩) 기준 6~12개월 목표가 — 상위 종목 클릭 모달에서 상승여력 % 자동 계산"],
            ["AI 신뢰도", "0~100점"],
          ]}
        />
        <H>AI 분석의 한계</H>
        <P>
          AI 요약은 점수·재무 데이터 기반이라 <Danger>최근 실적 발표, 돌발 뉴스, 경영진 교체</Danger> 같은
          최신 이벤트는 반영되지 않을 수 있습니다. 최신 흐름은 워치리스트의 네러티브 브리프(뉴스 기반)로
          보완하고, 중요한 포지션을 잡기 전에는 뉴스를 직접 확인하세요.
        </P>
        <Note>
          💡 AI 분석은 &quot;빠른 1차 검토&quot; 도구입니다. 최종 결정 전 직접 확인을 대체하지 않습니다.
        </Note>
      </>
    ),
  },
  {
    id: "position-calc",
    icon: "⊞",
    title: "포지션 계산기 — 적정 매수 수량 계산",
    subtitle: "고정 비율(Fixed Fraction)과 켈리 공식으로 수학적으로 결정",
    content: (
      <>
        <P>
          포지션 사이징은 매수 체크 탭 안에 있습니다. 감이 아닌 수학으로 몇 주를 살지 결정하는 도구로,
          티커·손절가를 입력하는 흐름 안에서 자동으로 계산됩니다.
        </P>
        <H>입력 항목</H>
        <Table
          headers={["입력값", "설명"]}
          rows={[
            ["포트폴리오 총액", "현재 계좌 총액 (원화 또는 달러)"],
            ["현재 주가",      "매수 예정가"],
            ["위험 허용 비율 (%)", "이 종목에서 감수할 최대 손실 비율. 보통 1~3%"],
            ["손절 비율 (%)",  "매수가 대비 손절 기준. 체제별 권장: risk_on -10%, neutral -8%"],
            ["승률 (%)",       "과거 또는 예상 승률 (켈리 공식에 사용)"],
            ["손익비 (R:R)",   "목표수익 ÷ 손절폭. 예: 목표 +15%, 손절 -7% → R:R = 2.1"],
          ]}
        />
        <H>① 고정 비율 (Fixed Fraction) — 보수적 방식</H>
        <P>
          위험 허용 금액을 손절 비율로 나눠 최대 투자금을 구합니다.
        </P>
        <div className="rounded-xl px-4 py-3 mt-2 font-mono text-[12px]" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: "#39ff8f" }}>
          위험 금액 = 총액 × 위험 허용 %<br />
          최대 투자금 = 위험 금액 ÷ 손절 %<br />
          매수 수량 = 최대 투자금 ÷ 현재가
        </div>
        <P>
          예: 총액 5,000만원, 위험 2%, 손절 7% →
          위험 금액 100만원 ÷ 7% = <Highlight>1,428만원 → 190주 (주가 75,000원)</Highlight>
        </P>
        <H>② 켈리 공식 (Kelly Criterion) — 수학적 최적</H>
        <P>
          기대 수익을 최대화하는 이론적 최적 비율을 계산합니다. 단, 최대 25% 상한으로 제한합니다.
        </P>
        <div className="rounded-xl px-4 py-3 mt-2 font-mono text-[12px]" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: "#39ff8f" }}>
          f = 승률 - (1 - 승률) / 손익비<br />
          투자 비율 = min(f, 25%)<br />
          매수 수량 = (총액 × 투자 비율) ÷ 현재가
        </div>
        <P>
          예: 승률 55%, 손익비 2.0 →
          f = 0.55 - 0.45/2.0 = 0.325 → <Highlight>25% 상한 적용 → 1,250만원 → 166주</Highlight>
        </P>
        <Note>
          💡 두 방식 중 <Warn>더 작은 수량</Warn>을 선택하는 것을 권장합니다.
          승률과 손익비가 낮으면 켈리 값이 음수가 나올 수 있는데, 이는 매수 비추천 신호입니다.
        </Note>
      </>
    ),
  },
  {
    id: "workflow-detail",
    icon: "▶",
    title: "매수 체크 심화 — 13개 조건의 의미",
    subtitle: "티커 입력 한 번으로 11개가 자동 판정되는 최종 관문",
    content: (
      <>
        <P>
          매수 체크 탭에 티커를 입력하면 13개 조건 중 <Highlight>11개를 실시간 데이터로 자동 판정</Highlight>합니다.
          수동 확인은 딱 2개 — &quot;워크북(정성 검증) 완료&quot;와 &quot;6개월 여유 자금&quot; — 항목을 클릭해서 직접 체크합니다.
          종목(티커)을 바꾸면 수동 체크는 자동으로 풀려요.
        </P>
        {[
          {
            n: "그룹 1", title: "시장 환경 (자동 4개)", auto: "자동",
            detail: "게이트 GO · 체제 Risk-on/Neutral · 리스크 허용 범위 · 선행 섹터 여부. 시장 자체가 나쁘면 종목이 좋아도 여기서 걸립니다.",
            go: "시장이 허락하는가",
          },
          {
            n: "그룹 2", title: "종목 검증 (자동 5개)", auto: "자동",
            detail: "워치리스트 후보 포함(재무 함정 필터 자동 통과) · BUY 액션 · Grade A/B · 점수 60+ · AI 분석 존재. 티커 입력 즉시 오늘 데이터와 대조됩니다.",
            go: "종목이 검증됐는가",
          },
          {
            n: "그룹 3", title: "정성 판단 (수동 2개)", auto: "수동",
            detail: "투자 워크북에서 스토리·촉매를 점검했는지, 6개월 이상 묶여도 되는 돈인지 — 시스템이 대신 판단할 수 없는 것들입니다. 클릭해서 체크하세요.",
            go: "내가 확신하는가",
          },
          {
            n: "그룹 4", title: "실행 준비 (입력 2개)", auto: "반자동",
            detail: "손절가를 입력하면 체제별 권장 손절선과 예상 손실 금액이 계산되고, 포지션 사이징 계산기로 자금·손실한도 기반 적정 수량을 역산합니다.",
            go: "얼마나 살 것인가",
          },
        ].map(({ n, title, auto, detail, go }) => {
          const autoColor = auto === "자동" ? "#39ff8f" : auto === "반자동" ? "#facc15" : "#9ca3af";
          return (
            <div key={n} className="rounded-xl p-3 mt-2" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className="text-[12px] font-black" style={{ color: "#39ff8f" }}>{n}</span>
                <span className="text-[12px] font-semibold text-white">{title}</span>
                <span className="text-[12px] font-bold px-1.5 py-0.5 rounded"
                  style={{ background: `${autoColor}18`, color: autoColor, border: `1px solid ${autoColor}44` }}>{auto}</span>
                <span className="ml-auto text-[12px] px-2 py-0.5 rounded-lg font-semibold" style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
                  GO: {go}
                </span>
              </div>
              <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>{detail}</p>
            </div>
          );
        })}
      </>
    ),
  },
  {
    id: "gate",
    icon: "⊡",
    title: "시장 게이트(Market Gate) — 진입 필터",
    subtitle: "종목 선택 전에 통과해야 하는 시장 전체 관문",
    content: (
      <>
        <P>
          시장 게이트는 <Highlight>지금 시장에 돈을 넣어도 되는 환경인가</Highlight>를 판단하는 최종 필터입니다.
          체제 분석·기술 지표·매크로 지표를 종합해 GO / CAUTION / STOP 중 하나를 출력합니다.
        </P>
        <Table
          headers={["판정", "의미", "대응"]}
          rows={[
            ["GO",      "시장 환경 양호, 진입 가능",        "워크플로우 다음 단계 진행"],
            ["CAUTION", "일부 지표 악화, 신중하게",          "포지션 50% 이하, 손절선 좁게"],
            ["STOP",    "복수 지표 경고, 진입 자제",         "신규 진입 보류, 기존 포지션 점검"],
          ]}
        />
        <H>체제와 게이트의 차이</H>
        <P>
          체제(regime)는 <Highlight>시장의 성격</Highlight>을 분류합니다 (risk_on / risk_off 등).
          게이트(gate)는 <Highlight>지금 당장 진입해도 되는가</Highlight>를 최종 판정합니다.
          체제가 risk_on이어도 게이트가 CAUTION이면 단기 과열이나 경고 신호가 있는 것입니다.
        </P>
        <Note>
          💡 체제 risk_on + 게이트 GO가 동시에 성립할 때 가장 신뢰도 높은 진입 환경입니다.
        </Note>
      </>
    ),
  },
  {
    id: "risk",
    icon: "⛨",
    title: "리스크 지표 해석 — VaR과 MDD",
    subtitle: "내 포트폴리오가 얼마나 위험한 상태인지 숫자로 읽기",
    content: (
      <>
        <H>VaR 95% (Value at Risk)</H>
        <P>
          <Highlight>95% 신뢰수준에서 하루 동안 발생할 수 있는 최대 예상 손실</Highlight>입니다.
          100일 중 95일은 이 수치 이하로 손실이 발생하고, 5일은 이보다 더 큰 손실이 생길 수 있다는 의미입니다.
        </P>
        <Table
          headers={["VaR 95%", "의미", "대응"]}
          rows={[
            ["< 1%",  "낮은 리스크, 안정적", "정상 운용 가능"],
            ["1 ~ 2%", "보통 수준",           "모니터링 유지"],
            ["> 2%",  "높은 리스크",          "포지션 축소 검토"],
          ]}
        />
        <H>MDD (Maximum Drawdown, 최대 낙폭)</H>
        <P>
          포트폴리오의 <Highlight>고점 대비 현재까지의 최대 하락폭</Highlight>입니다.
        </P>
        <Table
          headers={["MDD", "의미", "대응"]}
          rows={[
            ["< 5%",   "정상 범위",           "유지"],
            ["5 ~ 10%", "주의 구간",           "헤지 또는 비중 점검"],
            ["> 10%",  "경고 — 전체 재검토",  "손절선 재설정, 취약 종목 정리"],
            ["> 20%",  "위험 — 전략 재검토",  "대규모 비중 축소"],
          ]}
        />
        <Note>
          💡 손절선을 지키지 않으면 MDD가 계속 커집니다. 손절선은 &quot;틀렸을 때의 비용&quot;을 미리 정해두는 리스크 관리 도구입니다.
        </Note>
      </>
    ),
  },
  {
    id: "forecast",
    icon: "⟋",
    title: "SPY·KOSPI 예측 — 방향성 예측",
    subtitle: "개요 탭 우측의 지수 방향 예측 카드를 보조 지표로 활용하는 방법",
    content: (
      <>
        <P>
          개요 탭 우측의 예측 카드는 LightGBM 모델이 <Highlight>다음 5거래일(1주일) 동안 지수가 오를지 내릴지</Highlight>를 예측한 결과입니다.
          개별 종목이 아닌 시장 전체의 방향을 보는 모델이며, ML 데이터가 부족한 날은 체제 지표 기반 추정으로 대체됩니다(카드에 표시됨).
        </P>
        <H>확률 해석</H>
        <Table
          headers={["상승 확률", "의미", "대응"]}
          rows={[
            ["> 65%",  "강한 강세 신호",  "적극적 포지션 가능"],
            ["55~65%", "완만한 강세",     "표준 포지션"],
            ["45~55%", "방향 불명확",     "관망 또는 소규모만"],
            ["< 45%",  "약세 우세",       "신규 진입 자제"],
          ]}
        />
        <Note>
          💡 이 모델은 방향(오르냐 내리냐)만 예측합니다. 얼마나 오르는지는 알 수 없습니다.
          시장 전체 방향이 우호적인지 확인하는 보조 지표로만 활용하세요.
        </Note>
      </>
    ),
  },
  {
    id: "watchlist",
    icon: "🔖",
    title: "워치리스트 — 적합 점수와 네러티브 브리프",
    subtitle: "후보 50개가 어떻게 뽑히고, 팝업의 정보를 어떻게 읽는가",
    content: (
      <>
        <P>
          워치리스트는 매주 전체 유니버스를 2단계로 걸러 <Highlight>시장별 상위 50개 후보</Highlight>만 남깁니다.
        </P>
        <H>1단계 — 함정 필터 (탈락 기준)</H>
        <P>
          Piotroski F-Score 5 미만 · ROE 8% 미만 · 이자보상배율 1 미만(좀비기업) · 부채비율 200% 초과 ·
          영업현금흐름 2년 연속 적자 · 매출+순이익 3년 연속 동반 감소 — 하나라도 걸리면 탈락합니다.
          <Highlight> &quot;뭘 사라&quot;가 아니라 &quot;뭘 사지 마라&quot;를 걸러주는 수비 필터</Highlight>입니다.
        </P>
        <H>2단계 — 시장 적합 점수 (0~100)</H>
        <Table
          headers={["축", "배점", "측정 내용"]}
          rows={[
            ["품질",     "40점", "Piotroski · ROE · 이자보상배율 — 재무가 얼마나 탄탄한가"],
            ["모멘텀",   "35점", "3·6개월 지수 대비 상대수익률 — 시장이 지금 사주고 있는가"],
            ["체제 정합", "25점", "현재 체제와 종목 성격의 궁합 — 성장장엔 성장주, 방어장엔 배당주"],
          ]}
        />
        <P>
          모멘텀은 <Highlight>네러티브의 정량 지표</Highlight>입니다 — 시장이 스토리를 믿기 시작하면 가격에 먼저 나타나므로,
          재무만 좋고 시장이 외면하는 가치함정이 자연스럽게 뒤로 밀립니다.
        </P>
        <H>네러티브 브리프 읽는 법 (종목 클릭 팝업)</H>
        <Table
          headers={["항목", "해석"]}
          rows={[
            ["관심도 배지",  "🔥HOT = 시장이 활발히 거래하는 테마 / 🌤WARM = 꾸준한 관심 / ❄️COLD = 관심 밖"],
            ["▲ 관심도 상승", "COLD→WARM 같은 전환 — 시장이 스토리를 발견하기 시작했다는 조기 신호"],
            ["스토리",       "최근 1주 뉴스 기반 — 시장이 왜 이 종목에 관심을 갖는지(안 갖는지)"],
            ["다가오는 촉매", "실적발표·신제품·정책 등 — 6개월 내 촉매가 없으면 스토리가 식을 수 있음"],
            ["스토리가 깨지는 경우", "이 리스크가 현실화되는지 계속 확인 — 매도 판단의 기준"],
          ]}
        />
        <Note>
          💡 &quot;최근 뉴스 없음 · COLD&quot;도 정보입니다 — 시장 관심 밖이라는 뜻이므로, 지금 사면 오래 기다릴 각오가 필요합니다.
          마음에 드는 종목은 <Highlight>+ 추가</Highlight> 후 메모에 &quot;왜 담았는지&quot;를 남겨두세요. 나중에 스토리가 아직 유효한지 자문하는 기준이 됩니다.
        </Note>
      </>
    ),
  },
  {
    id: "faq",
    icon: "?",
    title: "자주 하는 실수와 주의사항",
    subtitle: "이것만 피해도 더 잘 쓸 수 있습니다",
    content: (
      <>
        {[
          {
            q: "체제가 risk_on이라고 무조건 매수한다",
            a: "체제는 환경 판단일 뿐입니다. 게이트 신호, 스크리닝 결과, 리스크 지표를 함께 확인해야 합니다. 매수 체크 탭의 13개 조건을 모두 통과한 후 매수하세요.",
            type: "warn",
          },
          {
            q: "AI 목표주가를 그대로 믿는다",
            a: "AI 목표주가는 6~12개월 참고용입니다. 팩터 점수·섹터 사이클·시장 체제를 종합해서 판단하세요. 특히 최근 실적 발표나 돌발 이슈는 반영되지 않을 수 있습니다.",
            type: "warn",
          },
          {
            q: "손절선을 무시하고 버틴다",
            a: "손절선은 감정이 아닌 규칙입니다. 손절선을 지키지 않으면 MDD가 걷잡을 수 없이 커집니다. 체제가 바뀔 때 손절선도 함께 조정하세요.",
            type: "danger",
          },
          {
            q: "포지션 크기를 감으로 결정한다",
            a: "매수 체크 탭의 포지션 사이징을 활용하세요. 고정 비율·켈리 검증 결과 중 더 작은 수량을 선택하면 리스크를 수학적으로 관리할 수 있습니다.",
            type: "warn",
          },
          {
            q: "데이터가 '—' 로 나와도 그냥 무시한다",
            a: "— 표시는 분석 파이프라인이 아직 실행되지 않았거나 실패했다는 뜻입니다. 사이드바 하단 신선도 점을 확인하고, 오래됐으면 GitHub → Actions → Daily Analysis → Run workflow로 재실행하세요.",
            type: "warn",
          },
          {
            q: "워치리스트에 없는 종목을 그냥 산다",
            a: "매수 체크에서 '워치리스트 후보 포함' 항목이 미통과로 뜹니다. 함정 필터에 걸렸거나(재무 위험) 적합 점수 상위 50 밖이라는 뜻이니, 워치리스트 탭에서 이유를 확인하고 그래도 사겠다면 근거를 워크북 메모에 남기세요.",
            type: "danger",
          },
          {
            q: "관심도 상승 배지를 보고 바로 추격 매수한다",
            a: "COLD→WARM 전환은 조기 신호일 뿐 매수 신호가 아닙니다. 네러티브 브리프의 촉매·리스크를 읽고, 워크북 정성 검증과 매수 체크를 거친 후 진입하세요.",
            type: "warn",
          },
        ].map(({ q, a, type }) => (
          <div key={q} className="rounded-xl p-3 mt-2" style={{
            background: "#222222",
            border: `1px solid ${type === "danger" ? "#ef444433" : type === "warn" ? "#facc1533" : "#272727"}`,
          }}>
            <p className="text-[12px] font-semibold mb-1" style={{ color: type === "danger" ? "#ef4444" : type === "warn" ? "#facc15" : "#e5e7eb" }}>
              ✗ {q}
            </p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-muted)" }}>{a}</p>
          </div>
        ))}
      </>
    ),
  },
];

export default function GuideDetailPage() {
  return (
    <div className="space-y-3 max-w-3xl">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-base font-bold text-white">세부 사용 설명서</h1>
          <span className="inline-block px-2 py-0.5 rounded-lg text-[12px] font-bold" style={{ background: "#39ff8f22", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
            DETAIL
          </span>
        </div>
        <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          각 기능의 원리와 해석 방법 · 항목을 클릭해서 펼쳐보세요
        </p>
      </div>

      <Accordion sections={SECTIONS} />

      <p className="text-[12px] text-center pb-4" style={{ color: "#4a4a4a" }}>
        AlphaDesk는 투자 참고 도구입니다. 최종 투자 판단과 책임은 항상 본인에게 있습니다.
      </p>
    </div>
  );
}
