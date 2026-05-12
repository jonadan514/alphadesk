# 페이지 구성 안내

각 탭(사이드바 메뉴)에 어떤 정보가 담겨 있는지 정리합니다.

---

## 개요 `/`

종합 대시보드. 다른 탭의 핵심 지표를 한 화면에 모아서 보여줍니다.

| 구성 요소 | 내용 |
|---|---|
| KPI 4-카드 | 종합 판단 (GO/CAUTION/STOP), 신뢰도, 스크리닝 종목 수, 시장 게이트 점수 |
| 핵심 체제 지표 | VIX·TREND·BREADTH·CREDIT·YIELD CURVE 센서 상태 |
| 상위 5 알파픽 | 복합 점수 기준 상위 5개 종목 (등급·섹터·점수·액션) |
| 종합 판단 카드 | GO/CAUTION/STOP 대형 텍스트, 게이트 점수 |
| AI 피드 | 상위 3개 종목 간략 요약 |

**데이터 소스:** `/api/data/market-gate`, `/api/data/regime`, `/api/data/index-prediction`, `/api/data/reports`

---

## 게시판 `/board`

날짜별 분석 리포트 아카이브. 최근 30개 리포트를 아코디언 형식으로 표시합니다.

| 구성 요소 | 내용 |
|---|---|
| 리포트 목록 | 날짜·Verdict 배지·체제·Pick 수 요약 행 |
| 상세 펼치기 | 체제·게이트·Verdict + Top 10 Picks 테이블 |

**데이터 소스:** `/api/data/reports?limit=30`

---

## 시장 체제 `/regime`

5-sensor 가중합으로 현재 시장이 어느 국면인지 판별합니다.

| 구성 요소 | 내용 |
|---|---|
| Hero | 현재 체제명 (risk_on / neutral / risk_off / crisis), 체제 점수, 신뢰도, 권장 전략 |
| 센서 그리드 | VIX (30%), TREND (25%), BREADTH (18%), CREDIT (15%), YIELD CURVE (12%) 각 점수 |
| 매크로 스냅샷 | VIX 수치, 10Y 금리, 신용 스프레드 등 원시 지표 |
| 파라미터 | 체제 판정에 사용된 임계값 설정 |

**데이터 소스:** `/api/data/regime`

---

## 상위 종목 `/top-picks`

6-factor 복합 점수 기준 스마트머니 상위 종목 테이블입니다.

| 구성 요소 | 내용 |
|---|---|
| 요약 카드 | 종목 수, Verdict, 체제, 생성 시각 |
| 종목 테이블 | 순위·티커·등급·복합점수·전략·기술·펀다·애널리스트·RS vs SPY·액션 |
| 점수 바 | 복합 점수 시각화 (최대 100 기준) |

**팩터 구성:**
- **기술 (Technical)** — 이동평균·RSI·MACD 등 기술적 지표
- **펀더멘털 (Fundamental)** — EPS 성장·PEG·ROE 등 재무 지표
- **애널리스트 (Analyst)** — 목표가 상승 여력·BUY 비율
- **상대강도 (RS)** — SPY 대비 상대 수익률
- **거래량 (Volume)** — OBV·거래량 추세
- **기관 (Institutional)** — 기관 보유 변화·스마트머니 흐름

**데이터 소스:** `/api/data/reports?limit=1`

---

## AI 분석 `/ai`

Gemini 2.5 Flash가 선별 종목별로 생성한 한국어 투자 분석 리포트입니다.

| 구성 요소 | 내용 |
|---|---|
| 요약 카드 (접기/펼치기) | 종목명·등급·신뢰도·추천 (BUY/HOLD/SELL) |
| 투자 thesis | AI가 판단한 핵심 투자 근거 |
| 성장 촉매 | 주가 상승을 이끌 요인 목록 |
| 리스크 요인 | 투자 시 주의해야 할 하방 위험 |

처음 3개 카드는 기본으로 펼쳐져 있고, 나머지는 클릭으로 열 수 있습니다.

**데이터 소스:** `/api/data/ai-summaries`

---

## 지수 예측 `/forecast`

LightGBM 분류 모델로 다음 주 SPY·QQQ 방향을 예측합니다.

| 구성 요소 | 내용 |
|---|---|
| SPY / QQQ 카드 | 방향 (강세↑/약세↓), 확률, 신뢰도, 핵심 드라이버 |
| 모델 정보 | CV 정확도, 학습일, 피처 수 |
| 예측 이력 차트 | SPY·QQQ 확률 추이 라인 차트 (최근 13주) |
| 예측 이력 테이블 | 날짜별 방향·확률 기록 |

**데이터 소스:** `/api/data/index-prediction`, `/api/data/prediction-history`

---

## ML 랭킹 `/ml`

LightGBM rank_xendcg로 학습한 모델의 20일 후 수익률 예측 순위입니다.

| 구성 요소 | 내용 |
|---|---|
| 예측 순위 테이블 | Rank·Symbol·Pred Score·Pred Rank·Grade·학습일 |
| 피처 중요도 | 상위 15개 피처와 중요도 수평 바 차트 |

학습 방식: TimeSeriesSplit 교차검증, 퀀타일(0-4) 정수 레이블

**데이터 소스:** `/api/data/gbm-predictions`

---

## 리스크 모니터 `/risk`

SPY 기준 포트폴리오 위험 지표와 체제별 Stop Loss 기준을 제공합니다.

| 구성 요소 | 내용 |
|---|---|
| KPI 4-카드 | 리스크 상태, 자산 배분 비율, VaR 95 (1일), 리스크 레벨 |
| Stop Loss 테이블 | 체제별 손절 기준·MDD 경고·전략 설명, 현재 체제 강조 표시 |

**주요 지표:**
- **VaR 95** — 95% 신뢰수준에서의 1일 최대 예상 손실
- **MDD** — 최대 낙폭 (Maximum Drawdown)

**데이터 소스:** `/api/data/risk`, `/api/data/regime`

---

## 성과 트래커 `/performance`

분석 리포트 기반 BUY 추천 이력을 추적합니다.

| 구성 요소 | 내용 |
|---|---|
| KPI 카드 | 성과 스냅샷 데이터 (있는 경우) |
| Pick 추이 차트 | 날짜별 전체 Pick 수 vs BUY Pick 수 라인 차트 |
| BUY 이력 테이블 | 날짜·Symbol·등급·점수·현재가·목표가·섹터 |

**데이터 소스:** `/api/data/performance`, `/api/data/reports?limit=60`

---

## 시스템 그래프 `/graph`

선별 종목을 섹터별 버블 차트로 시각화합니다.

| 구성 요소 | 내용 |
|---|---|
| 섹터 필터 | 버튼 클릭으로 특정 섹터만 필터링 |
| 버블 차트 | X축=섹터, Y축=복합점수, 버블크기=등급 (A가 가장 큼) |
| 종목 목록 | 점수 내림차순 테이블 (Symbol·Grade·Score·Sector) |

**데이터 소스:** `/api/data/graph`

---

## AI 빌더 `/ai-builder`

분석 파이프라인을 구성하는 에이전트 카드 목록입니다.

| 에이전트 | 스크립트 | 상태 |
|---|---|---|
| 통합 분석 파이프라인 | `scripts/run_integrated_analysis.py` | READY |
| 스마트머니 스크리닝 | `scripts/run_screening.py` | READY |
| 시장 체제 감지 | `src/analyzers/market_regime.py` | READY |
| 매크로 데이터 수집 | `src/collectors/macro_collector.py` | READY |
| ML 모델 훈련 | `src/ml/pipeline/train.py` | BETA |
| ML 예측 실행 | `src/ml/pipeline/predict.py` | BETA |
| AI 종목 요약 생성 | `src/analyzers/ai_summary_generator.py` | READY |
| SPY 방향 예측 | `src/us_market/index_predictor.py` | READY |
| Walk-Forward 검증 | `src/ml/validation/walk_forward.py` | BETA |
| 대시보드 JSON 재생성 | `scripts/regen_dashboard_data.py` | READY |

> 실행 버튼은 현재 UI 미리보기 전용입니다. 실제 실행은 터미널에서 직접 수행하세요.

---

## 다운로드 `/download`

분석 결과물을 JSON·CSV로 내려받습니다.

| 파일 | 형식 | 내용 |
|---|---|---|
| `sp500_list.csv` | CSV | S&P 500 503개 종목 리스트 |
| `smart_money_picks.json` | JSON | 최신 상위 종목 및 팩터 점수 |
| `latest_report.json` | JSON | 최신 통합 분석 리포트 전체 |
| `regime.json` | JSON | 현재 시장 체제 스냅샷 |
| `prediction_history.json` | JSON | 예측 이력 최대 100건 |
| `gbm_predictions.json` | JSON | LightGBM 예측 상위 종목 |

**데이터 소스:** 각 카드에 표시된 API 엔드포인트에서 실시간 로드

---

## API 비용 `/costs`

AI API 사용량과 비용을 추적합니다.

| 구성 요소 | 내용 |
|---|---|
| API 요금제 카드 | Gemini Flash·GPT-4o-mini·Perplexity Sonar 단가 |
| 예상 비용 | 20개 종목 1회 분석당 예상 비용 |
| 실제 사용 내역 | 날짜·서비스·모델·토큰 수·비용 상세 테이블 |

분석 실행 시 Gemini API `usage_metadata`에서 토큰 수를 자동 수집하여 기록합니다.

**데이터 소스:** `/api/data/costs`
