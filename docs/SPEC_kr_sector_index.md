# 한국 섹터 분석을 KRX 공식 지수로 교체

작성 2026-09-29. 조사 결과는 Actions 실행 두 건으로 실측한 것이다
(`probe-krx-sector-index.yml`, run 36508247206 / 36508496826).

## 1. 왜 바꾸나

`src/analyzers/kr_sector_analyzer.py`는 "한국에는 섹터 ETF가 없다"는 이유로
섹터마다 대표 종목 1-3개를 코드에 박아 두고(`SECTOR_ANCHORS`) 그 평균 수익률을
섹터 수익률로 쓴다. 미국 쪽(`sector_analyzer.py`)이 SPDR 11개 ETF를 쓰는 것과
대비된다.

문제는 이 앵커가 전부 사람이 고른 것이라는 점이다.

- `Utilities: ["015760.KS"]` - 한국전력 한 종목. 사실상 "한국전력 주가"를
  유틸리티 섹터라고 부르고 있다.
- `Technology`는 삼성전자·SK하이닉스·삼성SDI 3종목인데, 정규화 평균이라
  삼성전자 한 종목이 섹터를 끌고 간다.
- 어떤 종목을 넣고 뺄지에 대한 근거가 코드 주석 외에 없다.

KRX는 업종지수와 코스피200 섹터지수를 직접 산출해 공표한다. 그걸 쓰면 이
자의적 선택이 통째로 사라진다.

## 2. 조사 결과 (실측)

세 가지를 확인했다.

1. **지수 목록 조회** - 됨. KOSPI 53개, KOSDAQ 39개.
   pykrx 1.2.8 + KRX 로그인(`KRX_ID`/`KRX_PW`, Secrets에 있음)이 필요하다.
   로컬에는 자격증명이 없어 Actions에서만 확인 가능하다.
2. **과거 시세** - 됨. 150일 구간에 99 거래일이 돌아온다(RS 계산에 충분).
3. **이름 맞춰 붙이기** - **된다.** 이게 핵심이었다.

처음에는 업종지수(1005 음식료·담배, 1008 화학, 1013 전기전자 …)만 있는 줄
알았고, 그건 상장 구분에 가까워 GICS 계열인 앱 섹터와 일대일이 아니었다
(예: "운송장비·부품"에 현대차와 조선이 함께 들어간다).

그런데 목록에 **코스피200 섹터지수(1150-1160)** 가 따로 있었다. 이쪽은 GICS
계열이라 앱이 쓰는 이름과 거의 그대로 맞는다.

### 확정 매핑

| 앱 섹터 | 지수 | 이름 |
|---|---|---|
| Technology | 1155 | 코스피 200 정보기술 |
| Consumer Cyclical | 1158 | 코스피 200 경기소비재 |
| Consumer Defensive | 1157 | 코스피 200 생활소비재 |
| Financial Services | 1156 | 코스피 200 금융 |
| Industrials | 1159 | 코스피 200 산업재 |
| Healthcare | 1160 | 코스피 200 헬스케어 |
| Communication Services | 1150 | 코스피 200 커뮤니케이션서비스 |
| Basic Materials | 1153 | 코스피 200 철강/소재 |
| Energy | 1154 | 코스피 200 에너지/화학 |
| **Utilities** | **1017** | **전기·가스 (업종지수)** |
| (벤치마크) | 1001 | 코스피 |

11개 전부 99행, 서로 다른 종가 98-99개로 정상 산출 중인 것을 확인했다
(산출이 멈춘 지수는 행 수만 채워지고 종가가 굳어 RS가 조용히 0이 되므로
같이 확인했다).

### 솔직히 적어 둘 한 가지

Utilities만 코스피200에 해당 섹터가 없어 **다른 지수 계열**(전 코스피 업종지수)을
쓴다. 9개는 코스피200 구성종목 안에서, 1개는 전 코스피에서 산출된다는 뜻이다.
벤치마크(코스피) 대비 RS를 낼 때 미세한 비일관이 생긴다.

그래도 이 선택을 유지한다. 대안이 "한국전력 한 종목"이기 때문이다. 코스피200에
유틸리티 섹터지수가 없는 건 코스피200 안에서 유틸리티 비중이 작아서이고, KRX가
안 만든 것을 우리가 종목을 골라 만들면 지금 없애려는 바로 그 자의성이 돌아온다.

벤치마크는 코스피200(1028)이 아니라 **코스피(1001)** 를 쓴다. 9개 섹터만 보면
코스피200이 더 정확한 비교 대상이지만, 화면이 "코스피 대비"라고 말하고 있고
Utilities는 전 코스피 기준이라 그쪽이 오히려 덜 일관된다. 코스피와 코스피200의
수익률 차이는 작아 RS에 미치는 영향은 2차적이다.

## 3. 구조 - 왜 분석기가 pykrx를 직접 import하면 안 되나

두 가지가 막는다.

1. pykrx 1.2.8은 `pandas<3.0`을 요구하는데 이 저장소는 pandas 3.x다. 같은
   환경에 두면 pip이 에러 대신 pykrx를 1.0.51로 조용히 낮춘다(KRX 로그인
   기능이 없는 버전 -> 모든 조회 실패). `weekly-watchlist.yml`이 이미 겪은
   문제다.
2. KRX 로그인이 필요해 네트워크와 자격증명 없이는 돌지 않는다. 분석기가 직접
   부르면 테스트가 네트워크를 타야 한다(금지).

그래서 `fetch_kr_universe_pykrx.py`와 **같은 방식**을 쓴다: 격리 venv에서 도는
수집 스크립트가 JSON을 쓰고, 분석기는 그 JSON만 읽는다.

```
[격리 venv: pandas<3.0 + pykrx 1.2.8 + KRX 로그인]
  scripts/fetch_krx_sector_index.py  ->  krx_sector_index.json
                                              |
[본 환경: pandas 3.x]                          v
  kr_sector_analyzer._fetch_sector_data()  <- JSON을 pd.Series로
```

## 4. 구현 순서

### 4-1. `scripts/fetch_krx_sector_index.py` (신규)

격리 venv에서 돈다. `probe_krx_sector_index.py`의 `PROPOSED`/`BENCHMARK`를
가져다 쓰지 말고 **이 파일에 정본으로 옮긴다**(probe는 조사 기록이라 남겨 두되
운영 경로가 조사 스크립트를 import하게 만들지 않는다).

- 인자: `--out <경로>`, `--days <기본 150>`
- 각 지수의 일자별 종가를 받아 JSON으로 쓴다:
  ```json
  {
    "base_date": "20260928",
    "source": "krx",
    "pykrx_version": "1.2.8",
    "series": {
      "KOSPI":      {"ticker": "1001", "dates": ["2026-05-04", ...], "closes": [2801.1, ...]},
      "Technology": {"ticker": "1155", "dates": [...], "closes": [...]},
      ...
    }
  }
  ```
- 한 지수라도 실패하면 그 키를 **빼고** 나머지를 쓴다. 전부 실패하면
  0이 아닌 종료 코드로 끝낸다(워크플로가 폴백을 타도록).
- 자격증명은 설정 여부와 길이만 로그에 남긴다. 값은 절대 출력하지 않는다.

### 4-2. `kr_sector_analyzer._fetch_sector_data()` 교체

시그니처와 반환 타입(`dict[str, pd.Series]`, "KOSPI" 키 포함)은 **그대로 둔다**.
하위 계산(`_ret`, `_weekly_ret`, `analyze()`)은 손대지 않는다.

```python
def _fetch_sector_data(period: str = "4mo") -> dict[str, pd.Series]:
    series = _load_krx_index_series()      # 환경변수 KRX_SECTOR_INDEX_JSON
    if series:
        return series
    return _fetch_sector_data_yfinance(period)   # 기존 앵커 경로
```

- `KRX_SECTOR_INDEX_JSON`이 없거나 파일이 없거나 파싱 실패면 조용히 폴백한다.
- **기존 앵커 경로와 `SECTOR_ANCHORS`를 지우지 않는다.** 이름만
  `_fetch_sector_data_yfinance`로 바꿔 폴백으로 남긴다(KRX 로그인 만료나 KRX
  점검 때 섹터 분석 전체가 비는 것보다 낫다).
- `analyze()` 결과 payload에 `"sector_source": "krx" | "anchors"`를 넣는다.
  화면에서 어느 쪽으로 계산된 값인지 구분할 수 있어야 한다.

### 4-3. `weekly-analysis.yml`의 `kr-analysis` 잡

`Run KR analysis` 앞에 수집 단계를 넣는다.

```yaml
      - name: Fetch KRX sector index (isolated venv)
        continue-on-error: true      # 실패해도 앵커 폴백으로 분석은 돈다
        env:
          KRX_ID: ${{ secrets.KRX_ID }}
          KRX_PW: ${{ secrets.KRX_PW }}
        run: |
          python -m venv /tmp/krxenv
          /tmp/krxenv/bin/pip install --quiet "pandas<3.0" "pykrx==1.2.8"
          /tmp/krxenv/bin/python scripts/fetch_krx_sector_index.py --out /tmp/krx_sector_index.json

      - name: Run KR analysis
        env:
          KRX_SECTOR_INDEX_JSON: /tmp/krx_sector_index.json
        run: python scripts/run_kr_analysis.py
```

### 4-4. 테스트 (`tests/test_kr_sector_index.py` 신규)

네트워크·운영 DB·LLM을 타지 않는다. 임시 JSON 파일을 만들어 검증한다.

- JSON -> `pd.Series` 변환이 날짜 순서대로 되는가
- 섹터 키가 `SECTOR_ANCHORS`의 키 집합과 **정확히 일치**하는가
  (하나라도 어긋나면 `CYCLE_SECTORS`의 사이클 판정이 조용히 빈 값을 먹는다 -
  이게 이 교체에서 제일 조용하게 깨질 수 있는 자리다)
- `KRX_SECTOR_INDEX_JSON` 미설정/파일 없음/깨진 JSON 세 경우 모두 폴백을 타는가
- 일부 섹터만 들어 있는 JSON에서도 있는 것만으로 정상 동작하는가

## 5. 하지 않는 것

- **코스닥은 넣지 않는다.** 코스닥150 섹터지수(2212-2218)가 7개 있는 것은
  확인했지만, 지금 분석기는 코스피 전용이고(앵커가 전부 `.KS`, 벤치마크가
  코스피) 코스닥을 넣으면 벤치마크와 사이클 판정을 다시 설계해야 한다.
  별도 작업으로 둔다.
- **업종지수로 세분화하지 않는다.** 화학·전기전자 같은 업종지수를 여러 개
  묶어 섹터를 만들 수도 있지만, 묶는 가중치가 또 하나의 자의적 선택이 된다.
  KRX가 이미 묶어 놓은 코스피200 섹터지수를 그대로 쓴다.
- **미국 쪽(`sector_analyzer.py`)은 건드리지 않는다.** SPDR ETF는 잘 돌고 있다.
