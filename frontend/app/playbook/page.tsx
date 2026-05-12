"use client";

import Link from "next/link";
import FlagIcon from "@/src/components/FlagIcon";

const PORTFOLIO = [
  {
    title: "코어 70%",
    badge: "자동 적립",
    badgeColor: "#39ff8f",
    desc: "미국 지수 ETF (연금계좌)",
    detail: ["SPY · QQQ · VTI 등", "모니터링: 월 1회", "AlphaDesk 역할: 시장 체제 참고만"],
  },
  {
    title: "새틀라이트 30%",
    badge: "주간 관리",
    badgeColor: "#facc15",
    desc: "미국+한국 개별주 (1년 단위)",
    detail: ["미국 60-70% · 한국 30-40%", "총 4-5종목 이내", "종목당 새틀라이트 자금의 25% 이내"],
  },
];

const US_CRITERIA = [
  { label: "시장 체제 GO", tip: "CAUTION이면 신중, STOP이면 신규 매수 없음" },
  { label: "선행 섹터 종목", tip: "섹터 분석 기준 LEADING 뱃지 확인" },
  { label: "Composite Score 70 이상 (그레이드 A/B)", tip: "6팩터 합산 점수" },
  { label: "52주 고점 대비 -15% 이내", tip: "O'Neil — 바닥이 아닌 고점 근처에서 매수" },
  { label: "PEG 비율 1.0 미만", tip: "Lynch — 성장 대비 저평가 핵심 지표" },
  { label: "AI thesis 이해 가능한 비즈니스", tip: "이해 안 되면 스킵 (Lynch 원칙)" },
  { label: "손절가(-7~8%) 감내 가능한 금액", tip: "워크플로우 포지션 계산기에서 역산" },
];

const KR_CRITERIA = [
  { label: "한국 시장 체제 GO", tip: "risk_off이면 한국 비중 축소" },
  { label: "선행 섹터 종목", tip: "KR 섹터 분석 LEADING 섹터 우선" },
  { label: "Composite Score 70 이상 (그레이드 A/B)", tip: "4팩터 합산 점수" },
  { label: "PEG 비율 0.7 미만", tip: "한국 시장 기준 — 미국보다 엄격하게 적용" },
  { label: "EPS 성장률 +25% 이상", tip: "O'Neil CANSLIM 최소 기준" },
  { label: "AI 목표주가 상승여력 +15% 이상", tip: "종목 클릭 → 상세 모달에서 확인" },
  { label: "손절가(-7~8%) 감내 가능한 금액", tip: "워크플로우 포지션 계산기에서 역산" },
];

const RISK_RULES = [
  { icon: "🔴", title: "손절 절대 원칙", desc: "매수가 대비 -7~8% 도달 시 이유 불문 즉시 매도. 기다리면 더 커진다." },
  { icon: "📦", title: "종목당 최대 비중", desc: "새틀라이트 내 한 종목 최대 새틀라이트 자금의 25% 이내. 손절 나도 전체 자산 영향 최소화." },
  { icon: "🧩", title: "총 보유 종목 수", desc: "4-5종목 이내. 많을수록 관리 실패율 증가. 처음엔 2종목부터 시작." },
  { icon: "🌍", title: "시장 체제 STOP 시", desc: "신규 매수 없음. 기존 보유 종목 손절선만 관리. 현금 보유가 전략." },
  { icon: "⚖️", title: "한국 비중 조절", desc: "KR 체제 risk_off → 한국 비중 줄이고 미국으로 이동. KR risk_on 확인 후 복귀." },
  { icon: "📅", title: "보유 기간 기준 (새틀라이트)", desc: "개별주 최대 12개월. 단, 손절(-7~8%)·목표가 도달·테제 붕괴 발생 시 즉시 매도가 우선. 12개월은 '버텨도 되는 기간'이 아닌 '최대 상한선'." },
];

const SCORE_FACTORS = [
  { factor: "PEG < 1.0 (미국)", detail: "Lynch 핵심. +15점. 0.5 미만이면 +20점.", color: "#39ff8f" },
  { factor: "PEG < 0.7 (한국)", detail: "한국 시장 기준. +15점. 0.5 미만 +20점.", color: "#facc15" },
  { factor: "EPS 성장 +25%+", detail: "O'Neil 최소 기준. Fundamental에 +15점.", color: "#f97316" },
  { factor: "52주 고점 -5% 이내", detail: "O'Neil 돌파 신호. Fundamental에 +12점.", color: "#a78bfa" },
  { factor: "RS (상대강도)", detail: "S&P500·KOSPI 대비 20일 초과수익률 반영.", color: "#60a5fa" },
  { factor: "기관 보유율 80%+ (미국만)", detail: "스마트머니 동반 확인. Institutional에 +35점.", color: "#34d399" },
];

export default function PlaybookPage() {
  return (
    <div className="space-y-3 max-w-3xl">

      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ background: "#222222", color: "#6e6e6e" }}>
              STRATEGY REFERENCE
            </span>
            <h1 className="text-base font-bold text-white">투자 전략 플레이북</h1>
          </div>
          <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>
            Lynch + O'Neil 기반 원칙 · 실행은 워크플로우에서
          </p>
        </div>
        <Link href="/workflow"
          className="text-[12px] font-bold px-3 py-1.5 rounded-lg shrink-0"
          style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
          실행하기 →
        </Link>
      </div>

      {/* 포트폴리오 구조 */}
      <div className="rounded-xl p-4 space-y-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>포트폴리오 구조</p>
        <div className="grid grid-cols-2 gap-3">
          {PORTFOLIO.map(({ title, badge, badgeColor, desc, detail }) => (
            <div key={title} className="rounded-lg p-3" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[13px] font-bold text-white">{title}</span>
                <span className="text-[12px] font-bold px-2 py-0.5 rounded"
                  style={{ background: `${badgeColor}18`, color: badgeColor }}>{badge}</span>
              </div>
              <p className="text-[12px] mb-1.5" style={{ color: "#a8a8a8" }}>{desc}</p>
              {detail.map(d => (
                <p key={d} className="text-[12px]" style={{ color: "#6e6e6e" }}>· {d}</p>
              ))}
            </div>
          ))}
        </div>
        <div>
          <div className="h-2 rounded-full overflow-hidden flex" style={{ background: "#222222" }}>
            <div style={{ width: "70%", background: "#39ff8f", opacity: 0.7 }} />
            <div style={{ width: "18%", background: "#facc15", opacity: 0.8 }} />
            <div style={{ width: "12%", background: "#f97316", opacity: 0.8 }} />
          </div>
          <div className="flex gap-4 mt-1.5 text-[12px]" style={{ color: "#6e6e6e" }}>
            <span><span style={{ color: "#39ff8f" }}>■</span> 미국 지수 ETF 70%</span>
            <span><span style={{ color: "#facc15" }}>■</span> 미국 개별주 ~18%</span>
            <span><span style={{ color: "#f97316" }}>■</span> 한국 개별주 ~12%</span>
          </div>
        </div>
      </div>

      {/* 종목 선택 기준 */}
      <div className="grid grid-cols-2 gap-3">
        {[
          { mkt: "US" as const, label: "미국 개별주 선택 기준", criteria: US_CRITERIA, note: "PEG 1.0 미만 · 52주 고점 -15% 이내" },
          { mkt: "KR" as const, label: "한국 개별주 선택 기준", criteria: KR_CRITERIA, note: "PEG 0.7 미만 (한국 시장 엄격 기준)" },
        ].map(({ mkt, label, criteria, note }) => (
          <div key={label} className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
            <p className="flex items-center gap-1 text-[12px] font-bold uppercase tracking-widest mb-0.5" style={{ color: "#6e6e6e" }}>
              <FlagIcon market={mkt} size={13} /> {label}
            </p>
            <p className="text-[12px] mb-2" style={{ color: "#6e6e6e" }}>{note}</p>
            <div className="space-y-2">
              {criteria.map(({ label: cl, tip }, i) => (
                <div key={cl} className="flex gap-2.5">
                  <span className="text-[12px] font-black shrink-0 mt-0.5" style={{ color: "#4a4a4a" }}>{i + 1}</span>
                  <div>
                    <p className="text-[12px]" style={{ color: "#c0c0c0" }}>{cl}</p>
                    <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{tip}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 매수 결정 흐름도 */}
      <div className="rounded-xl p-4 space-y-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>매수 결정 흐름도</p>
        <p className="text-[12px]" style={{ color: "#6e6e6e" }}>이 순서를 따라가면 감에 의존하지 않고 체계적으로 매수할 수 있습니다.</p>
        <div className="space-y-1.5">
          {[
            { q: "마켓 게이트가 GO인가?",          yes: "다음 단계", no: "CAUTION→포지션 축소 / STOP→매수 없음",       color: "#39ff8f" },
            { q: "시장 체제가 risk_on 또는 neutral인가?", yes: "다음 단계", no: "risk_off→방어주만 / crisis→현금 보유", color: "#39ff8f" },
            { q: "선행 섹터(LEADING) 종목인가?",    yes: "우선 고려",  no: "다른 섹터면 점수 더 높아야 고려",           color: "#facc15" },
            { q: "Composite Score 70 이상(A/B등급)인가?", yes: "다음 단계", no: "60대→WATCH만 / 60미만→스킵",          color: "#facc15" },
            { q: "AI 분석을 읽고 테제를 이해했는가?", yes: "다음 단계", no: "이해 안 되면 스킵 (Lynch 원칙)",          color: "#facc15" },
            { q: "손절가(-7~8%) 금액을 감당할 수 있는가?", yes: "매수 진행", no: "포지션 크기를 줄이거나 스킵",        color: "#60a5fa" },
          ].map(({ q, yes, no, color }, i) => (
            <div key={i} className="rounded-lg p-3" style={{ background: "#111111", border: `1px solid ${color}22` }}>
              <p className="text-[12px] font-bold text-white mb-1.5">{i + 1}. {q}</p>
              <div className="flex gap-3">
                <div className="flex-1">
                  <span className="text-[11px] font-bold" style={{ color: "#39ff8f" }}>YES → </span>
                  <span className="text-[11px]" style={{ color: "#a8a8a8" }}>{yes}</span>
                </div>
                <div className="flex-1">
                  <span className="text-[11px] font-bold" style={{ color: "#ef4444" }}>NO → </span>
                  <span className="text-[11px]" style={{ color: "#a8a8a8" }}>{no}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 매도 기준 */}
      <div className="rounded-xl p-4 space-y-2" style={{ background: "#1c1c1c", border: "1px solid #ef444433" }}>
        <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>언제 팔아야 하는가</p>
        <div className="space-y-2">
          {[
            { trigger: "손절 (필수)", color: "#ef4444", desc: "매수가 대비 -7~8% 도달 시 이유 불문 즉시 매도. 예외 없음. '다시 오르겠지'는 손실 키우는 가장 흔한 실수." },
            { trigger: "목표가 도달",  color: "#39ff8f", desc: "AI 목표주가(상승여력)에 도달하면 절반 매도 또는 전량 매도 검토. 욕심은 수익을 돌려준다." },
            { trigger: "체제 악화",    color: "#facc15", desc: "보유 중 마켓 게이트가 STOP으로 바뀌면 신규 보유 종목부터 정리 검토. 시장 방향이 바뀌었다는 신호." },
            { trigger: "테제 붕괴",    color: "#f97316", desc: "실적 쇼크, 경영진 교체, 규제 이슈 등 매수 이유가 사라지면 가격 무관 매도. 스토리가 깨지면 주가도 깨진다." },
            { trigger: "12개월 경과",  color: "#9ca3af", desc: "보유 기간 최대 기준. 12개월 후 재검토하여 지속 보유 근거가 있는지 확인." },
          ].map(({ trigger, color, desc }) => (
            <div key={trigger} className="flex gap-3 rounded-lg px-3 py-2.5" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
              <span className="text-[12px] font-black shrink-0 w-20" style={{ color }}>{trigger}</span>
              <p className="text-[12px]" style={{ color: "#a8a8a8" }}>{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 실행 안내 */}
      <Link href="/workflow"
        className="flex items-center justify-between rounded-xl p-4 transition-all"
        style={{ background: "#39ff8f08", border: "1px solid #39ff8f22" }}>
        <div>
          <p className="text-sm font-bold" style={{ color: "#39ff8f" }}>실제 매수 전 — 워크플로우에서 확인하세요</p>
          <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>
            시장 신호 · 매수 전 체크리스트 · 포지션 사이징 계산기
          </p>
        </div>
        <span style={{ color: "#39ff8f" }}>→</span>
      </Link>

      {/* 리스크 관리 원칙 */}
      <div className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <p className="text-[12px] font-bold uppercase tracking-widest mb-2" style={{ color: "#6e6e6e" }}>리스크 관리 원칙</p>
        <div className="space-y-2">
          {RISK_RULES.map(({ icon, title, desc }) => (
            <div key={title} className="flex gap-3 rounded-lg px-3 py-2.5"
              style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
              <span className="text-base shrink-0">{icon}</span>
              <div>
                <p className="text-[12px] font-bold text-white mb-0.5">{title}</p>
                <p className="text-[12px]" style={{ color: "#a8a8a8" }}>{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Lynch/O'Neil 점수 반영 방식 */}
      <div className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <p className="text-[12px] font-bold uppercase tracking-widest mb-2" style={{ color: "#6e6e6e" }}>
          상위 종목 점수 — Lynch/O'Neil 반영 방식
        </p>
        <div className="grid grid-cols-2 gap-2">
          {SCORE_FACTORS.map(({ factor, detail, color }) => (
            <div key={factor} className="rounded-lg p-2.5" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
              <p className="font-bold text-[12px] mb-0.5" style={{ color }}>{factor}</p>
              <p className="text-[12px]" style={{ color: "#6e6e6e" }}>{detail}</p>
            </div>
          ))}
        </div>
        <p className="text-[12px] mt-2" style={{ color: "#4a4a4a" }}>
          * 상위 종목 상세 모달에서 PEG·EPS성장률·52주 고점 대비 수치를 직접 확인할 수 있습니다.
        </p>
      </div>

    </div>
  );
}
