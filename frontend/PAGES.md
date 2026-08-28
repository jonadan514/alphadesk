# 페이지 구성 안내

사이드바 탭별 내용과 데이터 소스 정리. (2026-08 기준 — 상세 사용법은 앱 내 가이드 탭 참고)

모든 시장 구분 페이지는 상단 탭으로 🇺🇸 미국 / 🇰🇷 한국을 전환한다 (`MarketContext`, localStorage 유지).

---

## 시장 분석

### 개요 `/`
이번 주 워치리스트 후보 수(순위 없음) 중심의 최소 화면. 주간 브리핑·섹터 분석으로 이동하는 링크.
- 소스: `/api/watchlist/candidates`

### 섹터 분석 `/sector`
경기 사이클 판단(회복/성장/과열/침체), 선행·후행 섹터(1개월 RS 상위/하위 3), 주간 RS 추이(4주), 섹터별 수익률·상대강도 히트맵(섹터 클릭 시 구성 종목).
- 소스: `/api/data/sector`, `/api/data/kr/sector`

## 내 투자

### 워치리스트 `/watchlist`
주간 스크리닝: 함정 필터(Piotroski·ROE·부채·현금흐름) 통과 종목을 순위 없이 리스트업(모멘텀 랭킹 없음 — 1~3년 펀더멘털 투자용). 종목 클릭 → 재무 지표 + 네러티브 브리프(장기 스토리·촉매·리스크·시장 단기 관심도 HOT/WARM/COLD·전일 대비 전환) + 종목별 정성 체크리스트(구 투자 워크북, stock_checklist에 독립 저장) + 매수 이유 메모.
- 소스: `/api/watchlist/{candidates,my,narrative,narrative-shifts,checklist}`

## 도구

### 성적표 `/scorecard`
과거 워치리스트 후보에 실제 주가를 대조한 사후 검증. 지수 단순 보유 vs 필터 통과 종목 균등매수 2-way 비교(30일~2년).
- 소스: `/api/data/scorecard`

### 가이드 `/guide` · 세부 설명서 `/guide/detail`
사용 설명서(3분 시작 가이드·매일 루틴·점수 구조) / 기능별 원리·해석법 아코디언.

---

## 백엔드 파이프라인 (GitHub Actions)

| 워크플로우 | 주기 | 하는 일 |
|---|---|---|
| Weekly Watchlist Screen | 일요일 22:00 UTC | 함정 필터 → 순위 없는 후보 리스트 갱신 → 네러티브 브리프 생성 → 주간 브리핑 |
| Weekly Market Analysis | 월요일 22:00 UTC | US/KR 섹터 분석 갱신 → 텔레그램 요약 발송 |
| Performance Tracking | 일요일 23:00 UTC | 과거 후보들의 30~730일 후 실제 수익률 계산 (성적표) |

데이터 저장소: Turso (libsql). 프론트는 읽기 전용 API로 접근.

**2026-08 제거**: 마켓 게이트·체제 판정·지수 예측(`/regime`), 리스크 분석(`/risk`), 페이퍼 포트폴리오·실거래 기록(`/portfolio`), 매수 체크(`/workflow`) — 순위 없는 리스트업 도구로 전환하며 정리. 배경은 `docs/radar/REMOVAL_PLAN.md` 참고.
