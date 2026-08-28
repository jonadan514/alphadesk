# 0번 기능 제거 — 조사 결과 (세션 1)

**작성일**: 2026-08-28
**범위**: `MASTER_PLAN_research_radar.md` §7의 제거 대상 실사. 코드는 건드리지 않았음.

---

## ⚠️ 먼저 확인 필요 — 실행 전에 결정할 두 가지 충돌

조사 중 마스터플랜 자체와 모순되는 지점 두 개를 발견했다. 이건 조사자(나)가 임의로
해석해서 진행하면 안 되는 부분이라, 세션 2(실행)로 넘어가기 전에 사용자 확인이 필요하다.

### 충돌 1. 마켓 게이트·체제판정을 지우면 "남는 화면"으로 지정된 `/briefing`이 깨진다

마스터플랜 §7은 "마켓 게이트 / 체제 판정 / 지수 예측"을 제거 대상으로 적었고, §7 맨
아래 "제거 후 남는 화면"에는 `/`, `/watchlist`, `/sector`, `/briefing`, `/guide`만
남는다고 적었다.

그런데 `frontend/app/briefing/page.tsx`는 게이트·레짐을 색깔 배지로 **직접 표시하는
화면**이다 (`m.gate`, `m.regime` 사용, `data_market_gate`/`kr_market_gate` 테이블
조회). `scripts/generate_weekly_briefing.py`와 `scripts/send_telegram_digest.py`도
같은 테이블에서 게이트·레짐을 읽어 주간 브리핑 텍스트와 텔레그램 다이제스트에 넣는다.

계산(Phase1: `market_regime.py`, `market_gate.py`, `index_predictor.py`, 그리고
KR쪽 `kr_market_regime.py`/`kr_index_predictor.py`)을 지우면 이 테이블들이 더 이상
갱신되지 않는다. 크래시는 안 나지만 **`/briefing`과 텔레그램 다이제스트가 마지막
계산값에 영원히 고정된 채로 계속 표시된다** — 에러 없이 조용히 낡은 정보를 보여주는
가장 나쁜 실패 형태다.

추가로: 이 프로젝트는 2026-08 초 리스트업 전환 때 이미 한 번 "게이트는 장기 매수를
막지 않는 참고 신호로 유지한다"고 정한 적이 있다(`docs/ALPHADESK_TOOL_OVERVIEW_2026-08.md`
참고). 이번 마스터플랜은 "계산만 하고 매수를 막지도 않았다"는 이유로 완전 삭제를
말하는데, 이게 예전 결정을 뒤집는 건지 아니면 그 결정을 몰랐던 건지 불명확하다.

**결정할 것**: 아래 셋 중 하나.
- (A) 게이트·체제판정·지수예측을 정말 전부 지운다 → `/briefing`과 텔레그램 다이제스트에서
  게이트·레짐 표시도 같이 뗀다 (`/briefing`이 "남는 화면"이되 내용은 바뀜)
- (B) 계산은 유지하되 매수 판단에서만 완전히 손을 뗀다 (지금 `execute_buys()`가 이미
  `gate` 파라미터를 사실상 무시하고 있으므로, 어차피 장식용 참고 정보로만 쓰는 셈)
- (C) 계산 로직은 지우고 `/briefing`·텔레그램은 "게이트" 대신 다른 걸로 대체한다

### 충돌 2. `/portfolio`는 통째로 지우면 안 된다 — 두 가지가 섞여 있다

`/portfolio` 페이지는 서로 다른 두 데이터를 같은 화면에 보여주고 있었다.

| 기능 | 데이터 | API | 제거 대상인가 |
|---|---|---|---|
| 페이퍼 포트폴리오 알림 | `portfolio_alerts` (tracker.py `check_alerts()`가 씀) | `/api/portfolio/alerts` | **그렇다** — 페이퍼 포트폴리오 4개와 함께 제거 |
| 실거래 기록 입력·조회 | `my_trades`, `trade_decision_snapshots` | `/api/trades`, `/api/trades/[id]`, `/api/portfolio/performance` | **아니다** — `scripts/compute_pick_returns.py`의 `run_trades()`가 이 테이블을 읽어 `my_trade_returns`를 만들고, 이게 `/scorecard`의 "3-way 비교"(필터 통과 종목 vs 지수 vs 실제 내 매매) 세 번째 축이다 |

마스터플랜 §7은 "`/portfolio` 실거래 기록 | 별도 대시보드로 분리하기로 결정"이라고
적어서, 지우는 게 아니라 **옮기는 것**이라고 스스로 밝혀두긴 했다. 문제는 옮길
별도 대시보드가 아직 없다는 것 — 지금 `/portfolio` 페이지를 그냥 지워버리면
**새 실거래를 입력할 방법 자체가 사라져서**, `/scorecard`의 3-way 비교 중 "실제
내 매매" 축이 그 시점부터 완전히 멈춘다 (기존 데이터는 안 지워지지만 갱신이 끊김).

**결정할 것**: 별도 대시보드가 준비될 때까지 `/api/trades` 입력 기능(과
`trade_decision_snapshots`)을 어디에 남겨둘지. 옵션:
- (A) `/portfolio` 페이지에서 페이퍼 포트폴리오 관련 위젯(알림)만 빼고, 실거래
  입력·조회 부분만 남긴 축소판으로 유지 (별도 대시보드 완성 전까지 임시로)
- (B) 지금 바로 `/api/trades`를 별도 대시보드(`invest-dashboard-orpin.vercel.app`,
  Navigation.tsx에 이미 링크된 "우리집 투자")로 넘긴다
- (C) 일단 `/portfolio` 전체를 지우고, 실거래 기록 자체를 몇 주 쉬어도 괜찮다고 본다
  (3-way 비교의 세 번째 축이 잠시 비는 것을 감수)

---

## 1. 제거 대상별 상세 — 어느 파일·워크플로에 걸쳐 있는가

### 1-1. 페이퍼 포트폴리오 4개 (`equal_1y`, `equal_3y`, `weighted_1y`, `weighted_3y`)

| 파일 | 역할 |
|---|---|
| `src/portfolio/tracker.py` | 전체 로직 (테이블 DDL, `execute_buys`, `execute_sells`, `check_alerts`, `snapshot`, `get_portfolio_summary`) |
| `scripts/run_integrated_analysis.py` Phase5·Phase6 | 매주 이 함수들을 호출 — **파일 자체가 아니라 US 일간 파이프라인 내부 함수 블록**임 |
| `src/risk/portfolio_risk.py` | `compute_risk()` — `pf_snapshots`/`pf_holdings` 기반으로 VaR·집중도 계산 (Phase6에서 호출) |
| `frontend/app/portfolio/page.tsx` | 표시 (단, 위 충돌 2 참고 — 전체 삭제 아님) |
| `frontend/app/api/portfolio/alerts/route.ts` | `portfolio_alerts` 조회 |
| `frontend/app/api/portfolio/performance/route.ts` | 이건 `my_trades` 조회라 **포트폴리오 제거와 무관, 남겨야 함** |
| DB 테이블 | `pf_portfolios`, `pf_holdings`, `pf_trades`, `pf_snapshots`, `pf_benchmark`, `portfolio_alerts`, `risk_portfolio`(portfolio_risk.py 출력) |

KR쪽(`scripts/run_kr_analysis.py`)에는 애초에 포트폴리오 매수 로직이 없다 — 대응
작업 없음.

### 1-2. 마켓 게이트 / 체제 판정 / 지수 예측

| 파일 | 역할 |
|---|---|
| `src/analyzers/market_regime.py` | US 체제 판정. `src/collectors/macro_collector.py` 사용 |
| `src/analyzers/market_gate.py` | US 게이트. `market_regime.py`를 import해서 재사용 |
| `src/us_market/index_predictor.py` | US 지수(SPY/QQQ) 방향 예측 |
| `src/analyzers/kr_market_regime.py` | KR 체제 판정 (독립 구현, USD/KRW 조회 인라인 포함) |
| `src/analyzers/kr_index_predictor.py` | KR(KOSPI) 지수 예측 (LightGBM) |
| `scripts/run_integrated_analysis.py` Phase1·Phase3 | US 호출부 + `data_daily_reports`/`data_regime`/`data_market_gate`/`data_index_prediction` 저장 |
| `scripts/run_kr_analysis.py` Phase1·Phase2·Phase5 | KR 호출부 + `kr_regime`/`kr_market_gate`/`kr_index_prediction`/`kr_daily_reports` 저장 |
| `src/db/data_store.py` | `upsert_regime`, `upsert_regime_history`, `upsert_market_gate`, `upsert_index_prediction`, `upsert_kr_index_prediction` |
| 프론트 API 8개 | `/api/data/{regime,market-gate,index-prediction,regime-history}`, `/api/data/kr/{regime,market-gate,forecast}` |
| 프론트 화면 | `/regime`(전용 화면), `/`(홈, 오늘의 판단에 사용), `/briefing`(⚠️ 충돌 1), `/workflow`(매수체크 조건에 사용) |

**`/regime` 화면 자체가 마스터플랜 §7 "제거 대상" 표에는 이름이 없지만, "남는 화면"
목록에도 없다.** 계산을 지우면 이 화면은 어차피 빈 화면이 되므로, 사실상 페이지도
같이 지우는 게 맞아 보인다 — 다만 이것도 마스터플랜에 명시되지 않은 추론이라 확인
받는 게 안전하다.

### 1-3. `/workflow` 매수체크

| 파일 | 역할 |
|---|---|
| `frontend/app/workflow/page.tsx` (1395줄) | 화면 전체. `market-gate`/`regime`/`index-prediction`/`risk`/`sector`/`watchlist candidates`/`check-log`/`fx` 등 9개 API를 동시에 호출하는 제일 무거운 페이지 |
| `frontend/app/api/workflow/check-log/route.ts` | `buy_check_log` 테이블 CRUD |
| DB 테이블 | `buy_check_log` |

`/workflow`는 마켓 게이트·리스크·섹터 데이터도 함께 쓰고 있어서, 1-2번(게이트)과
1-4번(리스크)이 없어지면 어차피 이 페이지는 반쯤 망가진다. 순서상 게이트·리스크
제거와 묶어서 처리하는 게 자연스럽다.

### 1-4. `/risk`

| 파일 | 역할 |
|---|---|
| `frontend/app/risk/page.tsx` (514줄) | 화면. `/api/data/risk`, `/api/data/risk-detail`, `/api/data/kr/risk` 호출 |
| `src/risk/portfolio_risk.py` | `compute_risk()` — 1-1(포트폴리오)에 종속. 포트폴리오가 없으면 계산할 대상 자체가 없어짐 |
| DB 테이블 | `risk_portfolio` (또는 `data_store.py`의 `upsert_risk` 대상 테이블 확인 필요 — Phase4의 SPY VaR/MDD와 이름이 겹치니 실행 세션에서 테이블명 재확인할 것) |

**주의**: `run_integrated_analysis.py` Phase4가 저장하는 "Risk"(SPY 기준 VaR95/MDD,
`upsert_risk`)와 Phase6 `compute_risk()`(포트폴리오 기준, `portfolio_risk.py`)가
이름이 비슷해서 실행 세션에서 헷갈리기 쉽다. Phase4의 SPY 전체시장 VaR/MDD는
포트폴리오와 무관하니 지울 필요 없을 수 있다 — 이것도 확인 대상.

### 1-5. `/portfolio` 실거래 기록

위 "충돌 2" 참고. 전체 삭제 대상이 아니라 분리 대상.

### 1-6. `weekly-analysis.yml`의 매수 실행 스텝

**이런 스텝은 워크플로 YAML 파일 안에 별도로 존재하지 않는다.** `weekly-analysis.yml`은
`us-analysis`/`kr-analysis` 잡에서 각각 `run_integrated_analysis.py`/`run_kr_analysis.py`를
한 번씩 실행할 뿐이고, "매수 실행"은 그 안의 Phase5(1-1 참고)다. 즉 이 항목은 YAML을
고칠 게 아니라 **1-1에서 `run_integrated_analysis.py`의 Phase5/6 블록을 들어내는 것과
동일한 작업**이다. YAML에서 딱 하나 고칠 것: 7번 줄 주석("...포트폴리오 매수에 반영할
수 있도록...")이 제거 후 의미가 없어지므로 정리.

---

## 2. 거시지표(금리·환율·유가 등) 수집 코드 중 재사용 가능한 것

| 코드 | 재사용성 | 비고 |
|---|---|---|
| `src/collectors/macro_collector.py` (`MacroDataCollector`) | **그대로 재사용 가능.** FRED(기준금리, 10Y-2Y 스프레드, 하이일드 스프레드), VIX, Fear&Greed를 각각 독립 메서드로 제공하는 순수 수집기 — regime 판정 로직과 분리돼 있다 | 현재 호출자는 `market_regime.py` 하나뿐이라, 그게 지워지면 당장은 아무도 안 부르는 상태가 된다. **삭제하지 말고 그대로 둘 것** — Phase 2 레짐 모듈에서 바로 import해서 쓸 수 있는 형태 |
| `src/analyzers/kr_market_regime.py`의 USD/KRW 조회 (65~84행) | **독립 모듈이 아니라 클래스 메서드 안에 인라인으로 박혀 있음.** 재사용하려면 `yf.Ticker("KRW=X").history(...)` 5줄을 별도 함수로 추출해야 함 | 로직 자체는 5~10줄짜리라 재사용보다 나중에 새로 짜는 게 더 간단할 수도 있다. 다만 "원화 약세=위험" 스코어링 임계값(20일 변화율 ±2%/±5%)은 이미 검증된 값이니, 지울 때 이 임계값 자체는 `themes.yaml` 스타일 주석으로라도 남겨두는 걸 권장 |
| Fed Funds/10Y-2Y/HY 스프레드 외 "환율·유가" | **유가(WTI 등) 수집 코드는 이 저장소에 없다.** 마스터플랜 "별도 처리 — 테마 아님" 섹션에 금리·환율·관세 등이 나열되지만 유가는 언급 안 됨 — 실제로 유가 데이터를 모으는 코드 자체가 없으므로 "재사용"할 것도 없음 (Phase 2 레짐 모듈에서 신규 개발 필요하면 그때 추가) | |

**결론**: 지울 때 `market_regime.py`, `market_gate.py`, `kr_market_regime.py`,
`index_predictor.py`, `kr_index_predictor.py` 자체는 삭제하되, **`macro_collector.py`는
파일째로 남긴다.**

---

## 3. `performance-tracking.yml`이 포트폴리오에 의존하는가

**의존하지 않는다. 확인 완료.**

`scripts/compute_pick_returns.py`가 읽는 것은 정확히 두 곳뿐이다:

1. `watchlist_candidate_history` (via `_load_candidate_history()`) — 매주
   워치리스트 스크리닝이 저장한 후보 스냅샷. `pf_*` 테이블은 전혀 참조하지 않는다.
2. `my_trades` (via `run_trades()`) — 이건 페이퍼 포트폴리오가 아니라 **실거래
   기록**이다. 그래서 "충돌 2"가 중요하다 — 포트폴리오(`pf_*`)를 지우는 것과
   `my_trades`를 지우는 것은 완전히 다른 일인데, `/portfolio` 페이지 하나에
   둘 다 얹혀 있어서 섞여 보일 뿐이다.

즉 **포트폴리오 4개를 통째로 지워도 `performance-tracking.yml`은 한 글자도
안 건드려도 된다.** 다만 `my_trades`로 이어지는 입력 경로(`/api/trades`)는
살려둬야 `run_trades()`가 계속 의미 있는 데이터를 받는다 (충돌 2 참고).

---

## 4. 결정 확정 (2026-08-28, 사용자 확인 완료)

1. **게이트·체제판정·지수예측 — 완전 삭제.** 계산 코드뿐 아니라 `/briefing`·
   텔레그램 다이제스트의 게이트·레짐 표시도 함께 제거한다. `/regime` 페이지도
   자동으로 제거 대상.
2. **`/portfolio` 실거래 기록 — 완전 삭제.** 별도 대시보드로 이관하지 않고
   기능 자체를 없앤다. `my_trades`, `trade_decision_snapshots` 테이블 참조와
   `/api/trades`, `/api/trades/[id]`, `/api/portfolio/performance` 라우트를
   제거한다.
3. **`/regime` — 삭제.** (1번의 직접 결과)
4. **`/risk` — 삭제.** Phase4(SPY 시장 VaR/MDD, `data_risk`)와 Phase6(포트폴리오
   리스크, `risk_portfolio`) 둘 다 `/workflow`·`/risk`(둘 다 제거 대상) 외에는
   소비하는 곳이 없음을 코드로 확인했다 (KR쪽 `/api/data/kr/risk`도 `kr_regime`
   파생이라 1번 결정에 이미 포함됨). 둘 다 제거.

### 2번 결정의 추가 파급 — 성적표 3-way가 2-way로 축소된다

`my_trades`를 없애기로 하면서 `scripts/compute_pick_returns.py`의 `run_trades()`
(→ `my_trade_returns` 테이블)도 더 이상 채울 데이터가 없어진다. 이건 §3에서 확인한
"performance-tracking.yml은 포트폴리오에 의존하지 않는다"는 결론과는 별개로, **이번
결정 때문에 새로 생기는 축소**다.

- `run_trades()` 함수와 `my_trade_returns` 테이블: 제거 대상에 추가
- `frontend/app/api/data/scorecard/route.ts`가 `my_trade_returns`를 조회해 3-way
  비교를 만드는 부분 제거 → **"필터 통과 종목 vs 지수" 2-way 비교로 축소**
- `/scorecard` 화면(204줄)에서 "내 실제 매매" 관련 표시 제거
- 기존에 쌓인 `my_trades`/`my_trade_returns` 데이터는 DB에서 DROP하지 않고 남겨둔다
  (마스터플랜 공통 원칙 — 나중에 필요해지면 그때 판단)

**`/scorecard` 자체는 지우지 않는다** — §0의 "충돌 1" 조사에서 확인했듯 이 화면은
`performance-tracking.yml`(마스터플랜이 명시적으로 보존하라고 한 "필터 검증 유일한
장치")의 사람이 보는 창구이므로, 내용만 3-way→2-way로 줄어들 뿐 화면은 유지한다.

---

## 5. 세션 2(실행) 착수 조건

위 4가지 결정이 모두 확정됐으므로 실행 세션으로 넘어갈 준비가 됐다. 실행 시 지울
목록(요약):

**삭제할 파일**
- `src/analyzers/market_regime.py`, `market_gate.py`, `kr_market_regime.py`,
  `kr_index_predictor.py`
- `src/us_market/index_predictor.py`
- `src/portfolio/tracker.py`
- `src/risk/portfolio_risk.py`
- `frontend/app/{workflow,risk,portfolio,regime}/page.tsx` 및 각 하위 디렉터리
- `frontend/app/api/{workflow,portfolio}/**`, `frontend/app/api/trades/**`
- `frontend/app/api/data/{regime,market-gate,index-prediction,regime-history,risk,risk-detail}/route.ts`
- `frontend/app/api/data/kr/{regime,market-gate,forecast,risk}/route.ts`

**남기는 파일 (재사용/무관)**
- `src/collectors/macro_collector.py` — Phase 2 레짐 모듈용으로 보존
- `scripts/compute_pick_returns.py` — `run_trades()`만 제거, 나머지 그대로
- `.github/workflows/performance-tracking.yml` — 변경 없음
- `frontend/app/scorecard/page.tsx`, `/api/data/scorecard` — 3-way→2-way로만 축소

**수정할 파일**
- `scripts/run_integrated_analysis.py` — Phase1(게이트/체제/지수예측), Phase4(SPY
  리스크), Phase5(포트폴리오 매수), Phase6(포트폴리오 리스크) 블록 제거. Phase0(데이터
  갱신), Phase3 중 리포트 저장 로직 축소, Phase7(섹터) 유지
- `scripts/run_kr_analysis.py` — Phase1(regime), Phase2(gate), Phase5(index
  prediction) 제거. Phase4(섹터) 유지
- `scripts/generate_weekly_briefing.py`, `scripts/send_telegram_digest.py` —
  게이트·레짐 표시 제거
- `frontend/app/page.tsx` (홈) — market-gate/regime/index-prediction fetch 제거,
  "오늘의 판단"을 다른 내용으로 대체 (레이더 Phase A 완성 전까지는 임시 문구 필요)
- `frontend/src/components/Navigation.tsx` — `/workflow`,`/portfolio`,`/risk`,
  `/regime` 메뉴 항목 제거
- `src/db/data_store.py` — `upsert_regime`, `upsert_regime_history`,
  `upsert_market_gate`, `upsert_index_prediction`, `upsert_kr_index_prediction`,
  `upsert_risk` 함수 제거 (호출부 없어지므로)
- `.github/workflows/weekly-analysis.yml` — 7번 줄 주석 정리 (매수 반영 언급 삭제)

**DB 테이블 — DROP 하지 않고 참조만 끊음**
`pf_portfolios`, `pf_holdings`, `pf_trades`, `pf_snapshots`, `pf_benchmark`,
`portfolio_alerts`, `data_regime`, `data_regime_history`, `data_market_gate`,
`data_index_prediction`, `kr_regime`, `kr_regime_history`, `kr_market_gate`,
`kr_index_prediction`, `data_risk`, `risk_portfolio`, `my_trades`,
`trade_decision_snapshots`, `my_trade_returns`, `buy_check_log`

이 목록으로 세션 2를 시작하면 된다.
