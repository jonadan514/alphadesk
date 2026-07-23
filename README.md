# AlphaDesk

개인용 미국(S&P 500)·한국(KOSPI) 주식 투자 의사결정 대시보드. 매크로 시장 체제 판단 →
종목 스크리닝 → AI 서사 분석 → 매수 체크리스트 → 포트폴리오/리스크 추적까지 하나의
파이프라인으로 묶은 개인 프로젝트입니다.

이 문서는 다른 AI 코딩 도구(Codex 등)로 이 프로젝트를 검토·작업할 때 빠르게 맥락을
잡을 수 있도록 작성되었습니다. 페이지별 상세 설명은 [`docs/PAGES.md`](docs/PAGES.md)를
참고하세요.

## 한눈에 보기

- **사용자**: 1인 개인 투자자 (실제 자산 운용에 사용 중)
- **대상 시장**: 미국 S&P 500 + 한국 KOSPI, 상단 탭으로 시장 전환
- **핵심 아이디어**: "지금 신규 진입해도 되는 시장인가?"(체제 게이트) → "된다면 어떤
  종목인가?"(스크리닝+AI) → "실제로 얼마나 사야 하는가?"(포지션 사이징 체크리스트)
- **운영 방식**: Python 배치 스크립트가 GitHub Actions 크론으로 매일/매주 자동 실행되어
  Turso(libSQL) DB에 결과를 적재하고, Next.js 프론트엔드가 그 결과를 읽어서 보여줌

## 아키텍처

```
GitHub Actions (cron)
  ├─ daily-analysis.yml   평일 07:30·16:30 KST — US/KR 분석 + 네러티브 + 텔레그램 다이제스트
  └─ weekly-watchlist.yml 매주 월 07:00 KST    — 워치리스트 스크리닝 + 주간 브리핑
        │
        ▼  (Python 스크립트가 결과를 적재)
Turso (libSQL, HTTP/Hrana v2)
        │
        ▼  (getClient()로 조회)
Next.js 15 (App Router) ── frontend/app/**/page.tsx
        │
        ▼
사용자 (브라우저) — https://alphadesk-eta.vercel.app, Vercel에 GitHub 연동 자동배포
```

- **프론트엔드**: Next.js 15 (App Router, React 19) + TypeScript + Tailwind. 페이지는
  전부 클라이언트 컴포넌트(`"use client"`)로 `fetch`를 통해 자체 API 라우트를 호출.
- **API 라우트**: `frontend/app/api/**/route.ts`, 전부 `export const dynamic =
  "force-dynamic"`. Turso를 직접 쿼리하거나 Yahoo Finance 등 외부 API를 그때그때 호출.
- **분석 엔진**: `src/` 하위 Python 모듈 (시장 체제 감지, 트랩 필터, 스크리닝, ML,
  포트폴리오 리스크 등) + `scripts/` 하위 실행 엔트리포인트.
- **DB**: Turso(libSQL). Python 쪽은 Hrana v2 HTTP 프로토콜로 raw `urllib.request`
  POST, Next.js 쪽은 `@libsql/client`(`src/lib/db.ts`의 `getClient()`).
- **배포**: Vercel, GitHub `main` 브랜치 push 시 자동 배포 (로컬 `.vercel` 링크 없음 —
  순수 Git 연동 방식).

## 디렉터리 구조

```
frontend/                 Next.js 앱
  app/
    page.tsx              개요(홈)
    briefing/             주간 브리핑
    regime/                시장 체제
    sector/                섹터 분석
    top-picks/             종목 분석 (스크리닝 상위 종목 + AI 분석)
    risk/                  리스크 모니터
    watchlist/             워치리스트 (스크리닝 후보 + 내 관심종목)
    portfolio/             포트폴리오 (실거래 기록 + 성과 비교)
    workflow/              매수 체크 (12조건 체크리스트 + 포지션 사이징)
    guide/                 사용 가이드
    api/                   백엔드 API 라우트 (DB 조회, 외부 시세 등)
  src/components/          공용 컴포넌트 (Navigation, StockTechPanel, MiniPortfolio 등)
  src/contexts/            MarketContext (미국/한국 전환 상태)
  src/lib/                 DB 클라이언트 등 유틸
  tailwind.config.ts       디자인 토큰(색상/라운드/폰트) — 전역 테마 소스
  app/globals.css          CSS 커스텀 프로퍼티 토큰

src/                       Python 분석 엔진
  analyzers/               시장 체제, 트랩 필터, 스크리닝, ML 랭킹, 리포트 생성 등
  collectors/               가격/재무 데이터 수집
  ml/                       LightGBM 기반 지수 방향 예측
  portfolio/, risk/         포트폴리오 추적, VaR/MDD 계산

scripts/                   실행 엔트리포인트 (run_kr_analysis.py, run_screening.py 등)
data/                      캐시된 가격/종목 리스트 (일부는 .gitignore 대상)
.github/workflows/         daily-analysis.yml, weekly-watchlist.yml
```

## 페이지 요약 (사이드바 순서)

| 메뉴 | 경로 | 한 줄 설명 |
|---|---|---|
| 개요 | `/` | 종합 판단(GO/CAUTION/STOP) + 체제 점수 + 상위 5종목을 한 화면에 |
| 주간 브리핑 | `/briefing` | 주간 스크리닝 결과를 읽기 쉬운 문서 형태로 요약 |
| 시장 체제 | `/regime` | risk_on/neutral/risk_off/crisis 판정과 근거 센서 분해 |
| 섹터 분석 | `/sector` | 섹터별 상대강도, 경기 사이클(early/mid/late/recession) |
| 종목 분석 | `/top-picks` | 6-factor(미국)/4-factor(한국) 스크리닝 상위 종목 + AI thesis |
| 리스크 | `/risk` | 실거래 기반 VaR, 섹터 집중도, 손절선 경보 |
| 워치리스트 | `/watchlist` | 함정 필터 통과 종목 후보 + 내가 담은 관심종목(메모·정성체크·네러티브) |
| 포트폴리오 | `/portfolio` | 실거래 기록 CRUD + 벤치마크 대비 성과 차트 |
| 매수 체크 | `/workflow` | 매수 전 12조건 체크리스트 + 손실 한도 기반 포지션 사이징 계산기 |
| 가이드 | `/guide`, `/guide/detail` | 앱 사용법·판단 기준 설명 (엔드유저용 문서) |

자세한 페이지별 레이아웃·데이터소스·로직은 [`docs/PAGES.md`](docs/PAGES.md) 참고.

## 디자인 시스템 (2026-07 개편)

최근에 전체 UI를 "터미널 앰버" 테마로 재작업했습니다:

- **팔레트**: 거의 검정에 가까운 배경(`#0a0a08`) + 종이빛 화이트 본문 텍스트 + 티커·순수
  숫자만 앰버(`#ffb020`/`#e3a63e`)로 강조하는 배색. 토큰은 `frontend/app/globals.css`
  (`:root` CSS 커스텀 프로퍼티)에 정의.
- **모서리**: `tailwind.config.ts`의 `borderRadius` 스케일을 전부 `0px`로 낮춰 각진
  룩을 전역 적용 (개별 `rounded-*` 클래스를 일일이 안 고쳐도 됨).
- **폰트**: `tailwind.config.ts`의 `fontFamily.sans`가 모노스페이스 스택을 최우선으로
  두고 한글은 Noto Sans KR로 자동 폴백.
- **색상 원칙**: 브랜드 액센트(`#ffb020`, 버튼·활성탭·오늘픽 배지)와 **실제 판단색**은
  분리되어 있음 — GO/BUY/risk_on/체크리스트 통과 같은 "좋음" 판단은 실제 초록
  (`#4ade80`)을 쓰고, warn(`#facc15`)/caution(`#fb923c`)/bad(`#f87171`) 4단계 시맨틱
  컬러가 별도로 존재. 정보성 보조색은 청록(`#6fb3b8`) 하나로 통일.
- 새 페이지나 컴포넌트를 만들 때 인라인 hex를 새로 만들지 말고 위 팔레트를 재사용할 것.

## 로컬 실행

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

- 환경변수는 `frontend/.env.local` (Turso URL/토큰, OpenAI API 키 등 — git에 안 잡힘)
- 프로덕션 빌드 검증: `npx next build` (커밋 전 항상 실행 — 과거 recharts 타입 에러가
  빌드에서만 잡힌 적 있음)

Python 분석 스크립트는 `requirements.txt` 기준 가상환경에서 `scripts/*.py`를 직접 실행
(로컬 테스트 시에도 Turso에 직접 씀 — 별도 로컬 DB 없음).

## 자동화 (GitHub Actions)

- **`daily-analysis.yml`**: 평일 US(16:30 KST)/KR(07:30 KST) 장 마감 후 분석 실행 →
  네러티브 브리프 생성 → 텔레그램 다이제스트 발송 (24시간 내 동일 내용이면 재발송 안 함)
- **`weekly-watchlist.yml`**: 매주 월요일 워치리스트 스크리닝 + 주간 브리핑 생성

## 알아두면 좋은 맥락

- KR 시장 체제는 20일 모멘텀 서킷브레이커(급락 시 즉시 crisis/risk_off로 강등)와 센서
  거부권(sensor veto) 로직이 있음 — 느린 가중평균만으로는 빠른 폭락을 못 잡는 문제를
  보완한 것 (`src/analyzers/kr_market_regime.py`, `scripts/run_kr_analysis.py`).
- 매수체크(`/workflow`)의 포지션 사이징 계산기는 원화 단일 입력을 받아 실시간 환율
  (`/api/fx/usdkrw`)로 자동 환산 — US/KR 시장 전환 시 통화 컨텍스트가 바뀌는 걸 놓치기
  쉬운 지점이라 과거에 버그가 여러 번 났던 자리.
- 포트폴리오 성과 차트(`/api/portfolio/performance`)는 US·KR 종목이 섞인 계좌일 경우
  주간 환율로 원화 환산 후 합산 — 통화를 안 맞추면 수익률이 크게 왜곡됨.
