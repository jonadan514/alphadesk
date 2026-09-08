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
              <span className="text-lg w-6 text-center shrink-0" style={{ color: "#ffb020" }}>{s.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-white">{s.title}</p>
                <p className="text-[12px] mt-0.5" style={{ color: "var(--text-muted)" }}>{s.subtitle}</p>
              </div>
              <span className="text-[13px] shrink-0 transition-transform duration-200" style={{
                color: "#ffb020",
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
  return <span className="font-semibold" style={{ color: "#ffb020" }}>{children}</span>;
}
function Warn({ children }: { children: React.ReactNode }) {
  return <span className="font-semibold" style={{ color: "#facc15" }}>{children}</span>;
}
function Danger({ children }: { children: React.ReactNode }) {
  return <span className="font-semibold" style={{ color: "#f87171" }}>{children}</span>;
}

const SECTIONS: Section[] = [
  {
    id: "screening",
    icon: "★",
    title: "재무 건전성 필터 — Piotroski F-Score란",
    subtitle: "점수로 줄 세우지 않고, 걸리면 탈락하는 방식으로 바뀐 이유",
    content: (
      <>
        <P>
          예전 버전은 기술·펀더멘털·상대강도·거래량 등을 가중 합산해 <Highlight>0~100점짜리 복합 점수</Highlight>를
          만들고 시장별 상위 50개만 후보로 남겼습니다. 1~3년 보유가 전제인 지금은 그 방식을 걷어내고,
          <Highlight> 재무가 건전한지만 걸러내는 함정 필터</Highlight>로 단순화했습니다 — 통과하면 순위 없이 전부 후보가 됩니다.
        </P>
        <Note>
          💡 처음엔 "명백히 위험한 것만 제외"하는 느슨한 기준(Piotroski≥5, ROE≥8% 등)이었는데,
          570종목 중 302개(53%)가 통과해 실사용에 너무 많았습니다. "확실히 우량한 것만 통과"로
          기준을 올려 지금의 값이 됐습니다.
        </Note>
        <H>탈락 기준 (하나라도 걸리면 제외)</H>
        <Table
          headers={["항목", "탈락 기준"]}
          rows={[
            ["Piotroski F-Score", "6점 미만 (아래 9개 항목 중 6개 미만 충족)"],
            ["이자보상배율(EBIT/이자비용)", "3배 미만 — 이자는 내지만 안전마진이 부족한 상태도 제외"],
            ["부채비율(총부채/자기자본)", "150% 초과 (금융업 제외)"],
            ["영업현금흐름", "최근 2년 연속 마이너스"],
            ["매출 + 순이익", "3년 연속 동시 감소 (매출만 2년 연속 감소도 별도 감점 사유)"],
            ["ROE", "미국 12% / 한국 8% 미만 (시장별 기준)"],
          ]}
        />
        <H>Piotroski F-Score 9개 항목</H>
        <P>재무제표 3개년(손익·재무상태·현금흐름)을 비교해 각 항목을 충족하면 1점씩, 최대 9점을 매깁니다.</P>
        <Table
          headers={["구분", "항목", "충족 조건"]}
          rows={[
            ["수익성", "ROA 양수", "총자산순이익률(ROA) > 0"],
            ["수익성", "영업현금흐름 양수", "CFO > 0"],
            ["수익성", "ROA 개선", "전년 대비 ROA 증가"],
            ["수익성", "이익의 질", "영업현금흐름 > ROA (회계상 이익보다 실제 현금흐름이 더 좋음)"],
            ["재무구조", "레버리지 감소", "부채비율(장기부채/자산) 전년보다 하락"],
            ["재무구조", "유동성 개선", "유동비율 전년보다 상승"],
            ["재무구조", "희석 없음", "발행주식수가 전년보다 늘지 않음"],
            ["운영효율", "매출총이익률 개선", "전년보다 상승"],
            ["운영효율", "자산회전율 개선", "전년보다 상승"],
          ]}
        />
        <Note>
          💡 이 필터는 <Highlight>&quot;뭘 사라&quot;가 아니라 &quot;뭘 사지 마라&quot;를 걸러주는 수비 필터</Highlight>입니다.
          통과했다고 반드시 좋은 투자처라는 뜻은 아니며, 어떤 종목을 실제로 살지는 네러티브 브리프와 본인의 판단으로 결정하세요.
        </Note>
      </>
    ),
  },
  {
    id: "ai",
    icon: "◎",
    title: "네러티브 브리프 — GPT 요약 자세히 읽는 법",
    subtitle: "워치리스트 종목 클릭 시 뜨는 뉴스 기반 투자 스토리 해석하기",
    content: (
      <>
        <P>
          GPT-4o mini가 종목별 최근 1주일 실제 뉴스 헤드라인을 읽고 <Highlight>이 종목에 대해 시장이 지금 무슨 이야기를 믿고 있는지</Highlight>를
          요약한 결과입니다. 재무 필터가 &quot;재무적으로 괜찮은가&quot;를 걸러낸다면, 네러티브 브리프는 &quot;시장이 왜 관심을 갖는지(또는 안 갖는지)&quot;를 알려줍니다.
        </P>
        <H>구성 항목</H>
        <Table
          headers={["항목", "내용"]}
          rows={[
            ["스토리 (Story)", "핵심 투자 스토리 2~3문장 — 이 회사의 장기 성장 동력/사업 구조가 왜 매력적인지(또는 우려되는지)"],
            ["촉매 (Catalysts)", "앞으로 1~3년 스토리에 영향을 줄 요인 최대 3개 — 구조적 성장동력·신사업·정책 변화 등 (단기 실적발표도 포함 가능하나 우선순위는 아님)"],
            ["리스크 (Risks)", "이 장기 스토리가 깨질 수 있는 근본적 리스크 최대 3개"],
            ["시장 단기 관심도", "🔥HOT · 🌤WARM · ❄️COLD — 최근 뉴스량 기준 보조 정보 (판단의 핵심 지표 아님)"],
            ["관심도 전환", "직전 갱신 대비 COLD→WARM 같은 상승 전환이 있으면 배지로 표시"],
          ]}
        />
        <H>한국 종목은 어떻게 다른가</H>
        <P>
          한국 종목은 구글 뉴스 한국어 검색(&quot;종목명 주가 OR 실적&quot;)으로 별도 수집합니다.
          나머지 요약 로직(스토리·촉매·리스크·관심도)은 미국과 동일합니다.
        </P>
        <H>네러티브 브리프의 한계</H>
        <P>
          뉴스 헤드라인 기반이라 <Danger>헤드라인에 없는 내용은 지어내지 않도록</Danger> 프롬프트가 제약돼 있습니다.
          최근 1주일간 뉴스가 없으면 &quot;최근 뉴스 없음&quot;으로 표시되는데, 이는 오류가 아니라
          <Highlight> 시장 관심 밖이라는 정보</Highlight>입니다. 매주 1회만 갱신되므로 그 사이의 급변 이슈는 직접 확인하세요.
        </P>
        <Note>
          💡 네러티브 브리프는 &quot;빠른 1차 검토&quot; 도구입니다. 중요한 포지션을 잡기 전에는 항상 원문 뉴스와 재무제표를 직접 확인하세요.
        </Note>
      </>
    ),
  },
  {
    id: "radar",
    icon: "📡",
    title: "테마 레이더 — 뉴스·실적·주가 세 축과 6개 라벨",
    subtitle: "종합 점수 없이, 정해진 조합에만 이름을 붙이는 이유",
    content: (
      <>
        <P>
          테마 레이더는 미국 시장의 산업 테마(AI 반도체·데이터센터 전력·조선 등 약 30개)를
          매주 <Highlight>뉴스·실적·주가 세 축</Highlight>으로 따로 관찰합니다. 워치리스트가
          &quot;이 종목이 재무적으로 건전한가&quot;를 본다면, 테마 레이더는 &quot;이 산업 전체가
          지금 어느 방향으로 움직이는가&quot;를 봅니다.
        </P>
        <Note>
          💡 세 축을 가중 합산한 점수는 만들지 않습니다. 각 축은 화살표(↑↑/↑/→/↓/–)로만 표시되고,
          정해진 조합에 맞을 때만 라벨을 붙입니다. 억지로 등수를 매기지 않는다는 원칙은
          워치리스트와 동일합니다.
        </Note>
        <H>세 축이 보는 것</H>
        <Table
          headers={["축", "측정 내용", "화살표 기준"]}
          rows={[
            ["뉴스", "이번 주 수집 기사 수 vs 직전 4주 평균", "급증(↑↑)·증가(↑)·보합(→)·감소(↓)"],
            ["실적", "소속 기업 중 매출 YoY 성장률이 \"같은 시장 중앙값\"을 넘는 비율", "과반 초과(↑)·그렇지 않음(↓)·표본부족(–)"],
            ["주가", "소속 기업 주가 수익률 중앙값 vs S&amp;P 500", "지수 초과(↑)·지수 미달(↓)"],
          ]}
        />
        <H>6개 라벨 조합</H>
        <Table
          headers={["라벨", "뜻"]}
          rows={[
            ["Quiet Strength", "뉴스는 잠잠하거나 줄었는데 실적은 실제로 개선 — 시장이 아직 못 알아챈 후보"],
            ["Quiet Recovery", "뉴스도 주가도 안 좋은데 실적은 개선 — 시장이 아직 못 따라잡았을 가능성"],
            ["Early Buzz", "뉴스가 급증했지만 실적은 아직 안 나옴"],
            ["Full Alignment", "뉴스·실적·주가가 다 같은 방향으로 움직임"],
            ["Overheated Buzz", "뉴스·주가는 뜨거운데 실적은 식음"],
            ["Full Decline", "세 축 다 하락"],
          ]}
        />
        <Note>
          💡 실적 축은 &quot;매출이 늘었는가&quot;가 아니라 &quot;같은 시장 기업들보다 잘했는가&quot;를
          봅니다. 절대 기준(성장률 &gt; 0)으로 재보니 미국 기업의 92%가 통과해서 거의 모든
          테마가 같은 값이 나왔고, 그래서 2026-09에 시장 중앙값 대비로 바꿨습니다.
          주가 축이 지수 대비 초과수익을 보는 것과 같은 방식입니다 — 대신 시장 전체가
          부진한 국면에서도 상위 테마는 상승으로 나올 수 있다는 점은 감안하세요.
        </Note>
        <Note>
          💡 6개 조합에 안 맞으면 라벨을 억지로 붙이지 않고 화살표만 남깁니다.
          &quot;라벨 없음&quot;은 오류가 아니라 그 자체로 정직한 결과입니다.
        </Note>
        <H>테마 카드를 펼치면</H>
        <P>
          소속 기업의 가치사슬 단계·근거·주력(direct)/일부(partial)/간접(peripheral) 구분·재무 통과
          여부까지 볼 수 있습니다. &quot;재무 통과&quot;는 워치리스트 스크리닝(재무 건전성 필터) 통과
          여부를 그대로 가져온 것입니다. 판정은 항상 <Highlight>통과 / 탈락 / 데이터 부족</Highlight>
          3분류이며, 탈락일 때는 어떤 기준에 걸렸는지(ROE·F-Score·부채 등)를 배지에 함께
          표시합니다. &quot;미확인&quot;은 <Danger>탈락이 아니라</Danger> 아직 스크리닝 대상이
          된 적이 없다는 뜻입니다(유니버스 밖 종목 등) — 확인 안 된 걸 탈락으로 단정하지 않습니다.
        </P>
        <Note>
          💡 미국·한국 두 시장을 지원합니다 — 상단 탭으로 전환하며, 각 시장은 그 시장의 지수
          (미국 S&amp;P 500 / 한국 KOSPI)와 비교합니다. 한국은 유니버스가 코스피 대형주 중심이라
          소속 기업이 5개 미만인 테마가 많고, 그런 테마는 실적·주가 축이 &quot;–&quot;(표본 부족)로
          남습니다. 홈 화면과 워치리스트 팝업(관련 테마 배지)에서도 이번 주 라벨을 확인할 수 있습니다.
        </Note>
      </>
    ),
  },
  {
    id: "watchlist",
    icon: "🔖",
    title: "워치리스트 — 후보는 어떻게 뽑히고 순위는 왜 없나",
    subtitle: "필터 통과 종목 전부를 보여주는 이유와 팝업 정보 읽는 법",
    content: (
      <>
        <P>
          워치리스트는 매주 전체 유니버스에 재무 건전성 필터(트랩 필터, 앞 섹션 참고)만 적용해
          <Highlight> 통과한 종목 전부</Highlight>를 후보로 남깁니다. 이전처럼 점수를 매겨 상위 N개로 자르지 않습니다.
        </P>
        <Note>
          💡 왜 순위를 없앴나 — 예전 방식(품질+모멘텀+체제 정합 점수로 상위 50개만)은 스크리닝 시점의 모멘텀에 크게 좌우됐습니다.
          1~3년 보유가 전제라면 그 순간의 모멘텀 순위가 실제 투자 성과와 크게 상관없다고 판단했습니다.
          지금은 재무가 건전한 회사인지만 걸러내고, 그 안에서 어떤 종목을 살지는 네러티브·섹터 분산·본인의 확신으로 직접 고릅니다.
        </Note>
        <H>네러티브 브리프 읽는 법 (종목 클릭 팝업)</H>
        <Table
          headers={["항목", "해석"]}
          rows={[
            ["관심도 배지",  "🔥HOT = 뉴스 많은 인기 테마 / 🌤WARM = 꾸준한 관심 / ❄️COLD = 관심 밖 — 보조 정보일 뿐 핵심 지표 아님"],
            ["▲ 관심도 상승", "COLD→WARM 같은 전환 — 시장이 스토리를 발견하기 시작했다는 조기 신호(참고용)"],
            ["스토리",       "최근 1주 뉴스 기반 — 이 회사의 장기 성장 동력이 왜 매력적인지(또는 우려되는지)"],
            ["다가오는 촉매", "앞으로 1~3년 스토리에 영향을 줄 요인 — 구조적 성장동력·신사업·정책 변화 등"],
            ["스토리가 깨지는 경우", "이 리스크가 현실화되는지 계속 확인 — 매도 판단의 기준"],
          ]}
        />
        <Note>
          💡 &quot;최근 뉴스 없음 · COLD&quot;도 정보입니다 — 시장 관심 밖이라는 뜻이므로, 지금 사면 오래 기다릴 각오가 필요합니다.
          마음에 드는 종목은 <Highlight>+ 추가</Highlight> 후 메모에 &quot;왜 담았는지&quot;를 남겨두세요. 나중에 스토리가 아직 유효한지 자문하는 기준이 됩니다.
        </Note>

        <H>정성 체크리스트 (팝업 하단)</H>
        <P>
          네러티브 아래에는 종목별로 독립 저장되는 3개 체크 항목이 있습니다 — 스토리를 한 문장으로 말할 수 있는지,
          스토리가 깨지는 조건을 아는지, 이 스토리가 1년 후에도 유효할 것 같은지(일시적 이슈가 아닌 구조적 동력인지).
          시스템이 자동으로 판정할 수 없는 <Highlight>정성적 판단</Highlight>만 모아뒀습니다 — 재무 필터처럼 숫자로
          이미 검증된 항목은 여기 다시 넣지 않았습니다. 원래 있던 &quot;6개월 내 촉매&quot;·&quot;관심도 상승 중인지&quot;
          두 항목은 바로 위 네러티브 브리프가 이미 자동으로 보여주는 것이라 2026-09에 뺐습니다.
        </P>
        <Note>
          💡 체크는 종목마다 따로 저장되므로 다른 종목을 봐도 섞이지 않습니다. 워치리스트에 추가한 종목은
          팝업 하단에서 매수 이유 메모도 바로 남길 수 있습니다.
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
            q: "시장 단기 관심도(HOT/WARM/COLD)만 보고 판단한다",
            a: "관심도는 최근 1주일 뉴스량 기준 보조 정보일 뿐, 장기 투자 판단의 핵심 지표가 아닙니다. COLD여도 장기 스토리는 탄탄할 수 있고, HOT이라고 재무가 좋은 것도 아닙니다. 판단의 중심은 항상 스토리·촉매·리스크입니다.",
            type: "warn",
          },
          {
            q: "관심도 상승 배지나 테마 레이더의 'Early Buzz' 라벨을 보고 바로 추격 매수한다",
            a: "둘 다 조기 신호일 뿐 매수 신호가 아닙니다. 네러티브 브리프의 촉매·리스크, 테마 카드의 소속 기업 근거를 직접 읽고 정성 체크리스트를 거친 후 본인이 판단하세요.",
            type: "warn",
          },
          {
            q: "테마 레이더에서 '미확인'으로 뜨면 재무가 부실한 종목이다",
            a: "미확인은 탈락이 아닙니다. 워치리스트 스크리닝이 이번 주 그 종목을 갱신 대상으로 다루지 않았거나 애초에 스크리닝 유니버스 밖이라는 뜻일 뿐, 재무를 직접 확인해본 결과가 아닙니다. 판정은 항상 통과/탈락/데이터부족 3분류입니다.",
            type: "warn",
          },
          {
            q: "성적표 수익률이 낮은 구간이 있으면 필터가 틀렸다고 결론짓는다",
            a: "성적표는 사후 검증용이고 표본수(n)가 적으면 노이즈가 큽니다. 이 도구는 1~3년 보유를 전제로 하므로 180일 이상 구간과 표본수를 함께 보고, 짧은 기간(30~90일) 성과만으로 필터를 판단하지 마세요.",
            type: "warn",
          },
          {
            q: "데이터가 '—' 로 나와도 그냥 무시한다",
            a: "— 표시는 해당 파이프라인이 아직 실행되지 않았거나 실패했다는 뜻입니다. 사이드바 하단 신선도 점을 확인하고(주 1회 갱신이라 7일 이내는 정상), 오래됐으면 GitHub → Actions에서 해당 화면의 워크플로우(섹터 분석은 Weekly Market Analysis, 테마 레이더는 Collect Theme News부터 순서대로)를 수동 재실행하세요.",
            type: "warn",
          },
        ].map(({ q, a, type }) => (
          <div key={q} className="rounded-xl p-3 mt-2" style={{
            background: "#262112",
            border: `1px solid ${type === "danger" ? "#f8717133" : type === "warn" ? "#facc1533" : "#111009"}`,
          }}>
            <p className="text-[12px] font-semibold mb-1" style={{ color: type === "danger" ? "#f87171" : type === "warn" ? "#facc15" : "#ece7d8" }}>
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
          <span className="inline-block px-2 py-0.5 rounded-lg text-[12px] font-bold" style={{ background: "#ffb02022", color: "#ffb020", border: "1px solid #ffb02044" }}>
            DETAIL
          </span>
        </div>
        <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
          각 기능의 원리와 해석 방법 · 항목을 클릭해서 펼쳐보세요
        </p>
      </div>

      <Accordion sections={SECTIONS} />

      <p className="text-[12px] text-center pb-4" style={{ color: "#423e33" }}>
        AlphaDesk는 투자 참고 도구입니다. 최종 투자 판단과 책임은 항상 본인에게 있습니다.
      </p>
    </div>
  );
}
