# AlphaDesk 스크리닝 필터 점검 — 2026-08-13

> 작성 경위: `ALPHADESK_IMPROVEMENT_PLAN.md`(2026-08-10, 배포 화면만 보고 작성됨) 검토 세션에서
> 이어진 논의. 이번엔 **실제 코드를 직접 열어서** 확인했다. 목적은 "지금 필터가 정확히
> 뭘 하는지"와 "그게 내가 원하는 투자 방향과 맞는지"를 판단하는 것.

---

## 왜 이 문서가 필요한가

`ALPHADESK_IMPROVEMENT_PLAN.md`의 "검증되지 않은 전제" 목록에 이런 항목이 있었다:

> 워치리스트 함정 필터가 실제로 부실 종목을 걸러낸다

이걸 확인하려고 실제 스크리닝 코드를 열어봤는데, **필터가 하나가 아니라 세 개였고, 그중
가장 중요한 화면(일간 BUY 픽)은 재무 건전성 필터를 아예 거치지 않는다는 걸 발견했다.**
아래는 그 상세 내용.

---

## 1. 구조 — 3층으로 분리되어 있다

```
[일간] EnhancedSmartMoneyScreener / KRStockScreener
  → S&P500(미국) / KOSPI 대형주 ~90개(한국) 안에서
  → 6팩터(미국) / 4팩터(한국) 가중합 점수
  → /top-picks 에 뜨는 BUY 액션의 근거
  (재무 건전성 하드 필터 없음 — 펀더멘털은 그냥 팩터 중 하나)

        ↓ (별도 파이프라인, 서로 안 이어짐)

[주간] trap_filter.py
  → S&P500+400(미국) / pykrx 전체(한국) — 더 넓은 유니버스
  → Piotroski F-Score 등 6~7개 조건, 하나라도 걸리면 즉시 탈락
  → 통과한 종목만 다음 단계로

[주간] market_fit_scorer.py
  → 함정 필터 통과 종목만 대상
  → 품질 40 + 모멘텀 35 + 현재 체제 궁합 25
  → /watchlist 워치리스트 후보 상위 50
```

**핵심: 이 세 파이프라인은 서로 독립적으로 실행된다.** 일간 스크리너가 주간 함정 필터의
결과를 참조하지 않는다. `scripts/run_integrated_analysis.py`, `scripts/run_kr_analysis.py`
(일간)는 `trap_filter.py`를 아예 import하지 않는다 — 코드에서 직접 grep해서 확인함.
`trap_filter.run_screen()`을 호출하는 곳은 `scripts/run_watchlist_screen.py`(주간) 단 한 곳.

---

## 2. 각 층 상세

### 2-1. 일간 스크리너 — `src/analyzers/smart_money_screener_v2.py` (미국)

유니버스: S&P 500만 (`scripts/run_integrated_analysis.py`의 `phase2_screening`이
`sp500_df["Symbol"]`을 그대로 넘김 — 중소형주 후보 자체가 없음)

| 팩터 | 가중치 | 내용 |
|---|---|---|
| 기술적 | 25% | RSI, MACD, 이동평균(20/50/200) 위치, 골든크로스 |
| 펀더멘털 | 20% | PER, EPS성장률, **PEG비율**(Lynch 스타일 GARP), ROE, 52주 신고가 근접도(O'Neil 스타일) |
| 애널리스트 | 15% | 컨센서스 등급, 목표가 대비 상승여력 |
| 상대강도 | 15% | 20일 수익률의 SPY 대비 초과분 |
| 거래량 | 15% | 최근 5일 거래량의 20일 평균 대비 Z-score (급증 여부) |
| 기관보유 | 10% | 기관 지분율 |

등급: 80점=A, 70=B, 60=C, 50=D, 그 미만=F. 코드 주석에 O'Neil, Lynch가 명시적으로 언급됨.

### 2-2. 일간 스크리너 — `src/analyzers/kr_screener.py` (한국)

유니버스: `src/collectors/kr_kospi_list.py`의 **고정 목록 ~90개 KOSPI 대형주** (섹터 태그
포함, pykrx 접근 안 되면 이게 기본값)

| 팩터 | 가중치 |
|---|---|
| 기술적 | 35% |
| 펀더멘털 | 20% |
| 상대강도(vs KOSPI) | 30% |
| 거래량 | 15% |

미국보다 기술적/상대강도 비중이 더 높다 — 모멘텀 의존도가 더 크다.

### 2-3. 주간 함정 필터 — `src/analyzers/trap_filter.py`

**하나라도 해당되면 탈락**(OR 조건, AND 아님):

1. 이자보상배율 < 1 (좀비기업)
2. 영업이익 적자
3. 영업현금흐름 2년 연속 마이너스
4. 부채비율 > 200% (금융업 제외)
5. 매출+순이익 3년 연속 동시 감소
6. 매출만 2년 연속 감소 (docstring에는 없는데 코드엔 있음 — 아래 3번 참고)
7. ROE < 8% (이것도 docstring에는 없음)
8. Piotroski F-Score < 5

Piotroski 자체가 9개 세부 항목(ROA 양수, CFO 양수, ROA 개선, 발생액, 레버리지 감소,
유동비율 개선, 무증자, 매출총이익률 개선, 자산회전율 개선)의 합.

### 2-4. 주간 적합 점수 — `src/analyzers/market_fit_scorer.py`

함정 필터 **통과한 종목만** 대상.

- 품질 40점 = Piotroski(20) + ROE(10) + 이자보상배율(10)
- 모멘텀 35점 = 3개월 지수대비 상대수익률(17.5, ±20% 클램프) + 6개월(17.5, ±30% 클램프)
- 체제 정합 25점 = 현재 시장체제(risk_on/neutral/risk_off/crisis) × 종목 성격(growth/dividend/neutral) 매칭표

---

## 3. 문서-코드 불일치 (참고용, 사소함)

`trap_filter.py` 맨 위 docstring은 "필터 순서 6개"라고 되어 있는데, 실제 코드는
"매출 2년 연속 감소"(단독)와 "ROE < 8%" 두 개가 더 있어서 사실상 7~8개 조건이다.
기능상 문제는 아니고 문서가 코드를 못 따라간 것.

---

## 4. 이 시스템의 전체적인 성향 (판단을 위한 요약)

- **모멘텀/추세추종 비중이 크다** — 상대강도, 거래량 급증, 이동평균 위치에 점수를 준다.
  "떨어지는 칼날 받기"보다 "이미 오르고 있는 것에 올라타기"에 가깝다.
- **가치투자여도 GARP(Growth At Reasonable Price) 쪽** — PEG 비율 중심. 순수 딥밸류(저PER
  자체를 노리는)나 배당/자산가치 중심 투자와는 결이 다르다.
- **대형주 전용** — 중소형주 발굴 기능이 없다. S&P500과 KOSPI 대형주 ~90개가 전부다.
- **일간 화면(가장 자주 보게 되는 `/top-picks`)은 재무 건전성이 "통과/탈락 게이트"가 아니라
  그냥 20%(미국)/20%(한국) 비중짜리 점수 하나다.** 기술적+모멘텀+애널리스트가 충분히
  좋으면 재무가 약해도 BUY로 뜰 수 있다.
- **재무 건전성을 진짜 하드 필터로 거르는 건 주간 워치리스트뿐이고, 그마저도 일간 화면과
  분리되어 있다.**

---

## 5. 다음 대화에서 판단해볼 것 (체크리스트)

- [ ] 일간 BUY 픽에 재무 건전성 게이트가 없는 게 의도한 설계인가, 아니면 사각지대인가?
      (원한다면 trap_filter를 일간 파이프라인에도 연결하거나, 최소한 red_flags를
      `/top-picks` 화면에 경고로라도 노출하는 방향을 검토할 수 있음)
- [ ] 모멘텀 비중(미국 15%+15%=사실상 기술적까지 합치면 더 큼, 한국은 35%+30%=65%)이
      내가 원하는 수준인가, 너무 추세추종에 치우쳤나?
- [ ] 대형주 전용이 맞는 전략인가, 중소형주 발굴을 원하는가?
      (원하면 유니버스를 S&P400/600, 코스닥으로 확장하는 작업이 필요함)
- [ ] PEG 기반 GARP 스타일이 내 투자 철학(가치/배당/성장 등)과 맞는가?
- [ ] 오늘 만든 `/scorecard`가 몇 달 데이터를 모으면, "등급별/게이트별 실제 수익률"로
      이 가중치들이 진짜 맞는지 숫자로 검증 가능해진다 — 이 대화의 결론을 그 검증
      계획과 연결해서 정리하면 좋음.

---

## 6. 참고 — 관련 파일 위치

```
src/analyzers/smart_money_screener_v2.py   미국 일간 스크리너 (6팩터)
src/analyzers/kr_screener.py               한국 일간 스크리너 (4팩터)
src/analyzers/trap_filter.py               주간 함정 필터 (Piotroski 등)
src/analyzers/market_fit_scorer.py         주간 적합 점수 (품질+모멘텀+체제)
src/collectors/kr_kospi_list.py            한국 대형주 고정 목록 (~90개)
scripts/run_integrated_analysis.py         미국 일간 파이프라인 (trap_filter 미사용)
scripts/run_kr_analysis.py                 한국 일간 파이프라인 (trap_filter 미사용)
scripts/run_watchlist_screen.py            주간 워치리스트 파이프라인 (trap_filter 사용)
```

저장소: `jonadan514/alphadesk` (Vercel: alphadesk-eta.vercel.app)
