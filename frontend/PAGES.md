# 페이지 구성 안내

사이드바 탭별 내용과 데이터 소스 정리. (2026-07 기준 — 상세 사용법은 앱 내 가이드 탭 참고)

모든 시장 구분 페이지는 상단 탭으로 🇺🇸 미국 / 🇰🇷 한국을 전환한다 (`MarketContext`, localStorage 유지).

---

## 시장 분석

### 개요 `/`
종합 대시보드 — 마켓 게이트(GO/CAUTION/STOP), 체제 점수, 핵심 체제 지표(센서), 지수 주요 지표(지수·SMA200·변동성·모멘텀), SPY/KOSPI 방향 예측, 상위 5픽, 내 포트폴리오 미니 카드.
- 소스: `/api/data/{market-gate,regime,reports,index-prediction}` · KR은 `/api/data/kr/*` + `/api/data/kr/forecast`

### 시장 체제 `/regime`
5센서 가중합 체제 판별(risk_on/neutral/risk_off/crisis), 체제별 행동 가이드·손절선·권장 비중, 센서 상태, 매크로 스냅샷(US 자체 / KR은 글로벌 매크로 + USD/KRW).
- 소스: `/api/data/regime`, `/api/data/kr/regime` (KR 페이지는 US regime도 로드해 매크로 표시)

### 섹터 분석 `/sector`
경기 사이클 판단(회복/성장/과열/침체), 선행·후행 섹터(1개월 RS 상위/하위 3), 주간 RS 추이(4주), 섹터별 수익률·상대강도 히트맵(섹터 클릭 시 구성 종목).
- 소스: `/api/data/sector`, `/api/data/kr/sector`

### 종목 분석 `/top-picks`
매일 갱신되는 발굴 레이더 — 복합 점수(US 6팩터/KR 4팩터) 상위 종목 테이블. 종목 클릭 시 상세 모달(가격·목표가·Lynch/O'Neil 지표·팩터·AI 분석). 내 워치리스트 종목엔 🔖 배지.
- 소스: `/api/data/reports`, `/api/data/ai-summaries`, `/api/data/sector` (KR 동일 구조)

### 리스크 `/risk`
⚠ 시스템 시뮬레이션 포트폴리오(가상 $100k 페이퍼 트레이딩) 기준 — 상단 배너에 명시.
건강도·VaR·알림·보유 현황·섹터 분산·상관관계 쌍·리스크 기여도·낙폭 분석.
실보유 5개 이상 쌓이면 my_trades 기반으로 전환 예정 (코드 TODO 참고).
- 소스: `/api/data/risk-detail`, `/api/data/kr/risk`

## 내 투자

### 워치리스트 `/watchlist`
주간 스크리닝: 함정 필터(Piotroski·ROE·부채·현금흐름) → 시장 적합 점수(품질40+모멘텀35+체제25) 시장별 상위 50 후보. 종목 클릭 → 재무 지표 + 네러티브 브리프(스토리·촉매·리스크·관심도 HOT/WARM/COLD·전일 대비 전환). 오늘픽 배지, 내 목록 메모, 관심도 상승 배너.
- 소스: `/api/watchlist/{candidates,my,narrative,narrative-shifts}`

### 포트폴리오 `/portfolio`
실거래 기록(매수/매도) + 현재가·평가손익 실시간 표시(Yahoo), 시장별 합계, 체제별 손절선 접근/도달 경고. 성과 비교 탭: 첫 거래=100 기준 벤치마크 대비 누적 수익률 차트.
- 소스: `/api/trades`, `/api/portfolio/prices`, `/api/portfolio/performance`, `/api/data/{regime,kr/regime}`

### 투자 워크북 `/workbook`
종목 정성 검증 노트 — 스토리·촉매 등 시스템이 자동 판정 못 하는 체크리스트 + 메모. (시장 환경·재무 검증은 매수 체크가 자동 수행)
- 소스: `/api/workbook/checklist`

## 도구

### 매수 체크 `/workflow`
주문 직전 최종 관문. 6단계 시장 신호 + 티커 입력 시 13개 조건 중 11개 자동 판정(게이트·체제·워치리스트 포함·BUY·등급·점수·선행섹터·AI·리스크·손절가·수량), 수동 2개(워크북 완료·여유 자금)는 클릭 체크. 포지션 사이징(고정 비율 역산 + 켈리 검증).
- 소스: 개요·섹터·AI·워치리스트 API 종합

### 가이드 `/guide` · 세부 설명서 `/guide/detail`
사용 설명서(3분 시작 가이드·매일 루틴·점수 구조) / 기능별 원리·해석법 아코디언.

---

## 백엔드 파이프라인 (GitHub Actions)

| 워크플로우 | 주기 | 하는 일 |
|---|---|---|
| Daily Analysis | 평일 2회 (KST 07:00·16:30) | US/KR 분석 → 네러티브 브리프 생성 → 텔레그램 요약 발송 |
| Weekly Watchlist Screen | 일요일 22:00 UTC | 함정 필터 + 적합 점수 → 후보 50×2 갱신 |

데이터 저장소: Turso (libsql). 프론트는 읽기 전용 API로 접근.
