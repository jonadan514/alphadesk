# 회귀 테스트 계획 (작업지시서 Phase 1)

완성본: `tests/test_dart_financials.py` (19케이스 통과). **나머지 파일은 이 파일의 형식을
그대로 따른다** - 가짜 입력으로 계산 규칙만 검증하고, 네트워크·운영 DB·LLM은 절대 쓰지 않는다.

실행:
```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

한글 테스트 이름을 쓴다(`def test_4분기는_연간에서_3분기_누적을_뺀다`). 실패했을 때 어떤
규칙이 깨졌는지 비개발자도 읽을 수 있어야 한다.

---

## 1. `tests/test_quarterly_financials.py` — 분기 재무 저장

대상: `src/db/quarterly_financials.py` (`ensure_schema`, `upsert_quarter`, `get_quarters`)
`memory_db` 픽스처를 쓴다.

| 케이스 | 기대 |
|---|---|
| 새 분기 저장 후 조회 | 넣은 값 그대로, `source`/`fs_div`/`derived` 보존 |
| 같은 분기를 비어 있는 값으로 다시 저장 | 기존 값 유지(덮어쓰지 않음) |
| 처음에 `revenue=None`, 나중에 값이 들어옴 | 비어 있던 칸만 채워짐 |
| 최신순 정렬 | `get_quarters`가 연도·분기 내림차순 |

**주의**: Phase 3에서 이 파일의 저장 규칙이 바뀐다(별도재무로 먼저 저장된 분기를 나중에
연결재무로 갱신해야 함). Phase 3 작업자는 위 2번째 케이스를 **"같은 fs_div일 때만 유지,
OFS→CFS면 갱신"** 으로 고쳐 쓴다. 지금은 현재 동작을 그대로 고정해 둔다.

## 2. `tests/test_mapping_validation.py` — 매핑 코드 검증 (작업지시서 16장)

대상: `scripts/map_theme_companies.py` (`validate_members`, `_evidence_subject_mismatch`,
`industry_theme_conflict`)

| 케이스 | 입력 | 기대 |
|---|---|---|
| 티커 실재 | universe에 없는 티커 | 제외, `stats["티커실재실패"]` 증가 |
| evidence 길이 | 15자 미만 근거 | 제외 |
| 근거 주어 불일치 | ticker=000660(SK하이닉스), 근거가 "SK이노베이션은..." | 제외 |
| 금지 문구 | "관련주"·"테마주"·"수혜 예상" 포함 | 제외가 아니라 `flagged=True` (현재 동작 유지) |
| linkage 이상값 | `linkage="strong"` | `"partial"`로 대체 |
| 업종-테마 불일치 | 보험사를 battery에 | `industry_theme_conflict`가 업종명 반환 |
| 업종 허용 | 식품사를 k_food에 | `None` 반환(허용) |
| **시장 오판(Phase 2에서 추가)** | 아래 참조 | |

**시장 오판 테스트는 Phase 2 수정과 함께 쓴다.** 반드시 아래 케이스를 넣는다.

```text
US 종목(시총 30억 달러 = 3e9)을 LLM이 market="KR"로 답함
  현재 코드: KR_MIN_CAP(2e11)과 비교 -> 시총 미달로 부당 탈락
  고친 뒤:   유니버스 기준 US로 확정 -> US_MIN_CAP(2e9) 통과
```

KR 종목을 US로 오판하는 반대 케이스는 통화 차이 때문에 증상이 안 나타난다(원화 시총이
달러 기준 하한보다 늘 크다). **라벨만 확인하는 테스트로는 이 버그를 못 잡는다.**

## 3. `tests/test_theme_earnings.py` — 실적 축

대상: `src/analyzers/theme_earnings.py`

| 함수 | 케이스 | 기대 |
|---|---|---|
| `yoy_growth` | 5분기 미만 | `None`(데이터부족, 탈락 아님) |
| `yoy_growth` | 1년 전 매출 0 또는 음수 | `None` |
| `market_median_growth` | 표본 `MIN_MEDIAN_SAMPLE`(20) 미만 | `None` |
| `classify_company_earnings` | 성장률 > 기준 | `improved` |
| `compute_earn_signal` | 판정 가능 기업 5명 미만 | `arrow="na"` |
| `compute_earn_signal` | `insufficient` 비율 40% 초과 | `arrow="na"` |
| `compute_earn_signal` | 개선 비율 0.7/0.55/0.45 경계 | `up2`/`up1`/`down` |

## 4. `tests/test_theme_price.py` — 주가 축

대상: `src/analyzers/theme_price.py` (`compute_price_signal`)

| 케이스 | 기대 |
|---|---|
| 가격 확보 5명 미만 | `arrow="na"`, `median_ret=None` |
| 지수 수익률 `None` | `arrow="na"` |
| 초과수익 +8%p / +3%p / -3%p 경계 | `up2` / `up1` / `down` |
| 중앙값을 쓴다 | 한 종목만 +200%여도 중앙값이 안 흔들림 |
| 거래대금 표본 5개 미만 | `volume_ratio=None` |

## 5. `tests/test_theme_labels.py` — 6개 라벨

대상: `src/analyzers/theme_labels.py` (`compute_label`)

SPEC 표 6줄을 그대로 케이스로 넣고, **축이 하나라도 `na`/`None`이면 라벨 없음**과
**표에 없는 조합이면 `None`** 을 반드시 포함한다.

## 6. `tests/test_decision_ledger.py` — 판정 원장 (작업지시서 17장)

대상: `scripts/build_decision_ledger.py` (`_walk`, `_market`),
`scripts/apply_decision_ledger.py` (`needs_look`, `both_axes_failed`)

| 케이스 | 기대 |
|---|---|
| `_walk`가 exclude/unapprove를 읽음 | `decision="exclude"` |
| `_walk`가 keep/restore/approve/items를 읽음 | `decision="keep"` |
| 이유에 "판단보류" 포함 | `decision="hold"` |
| `_market` | 6자리 숫자 코드 → KR, 영문 티커 → US |
| `needs_look` | `contradicts` 또는 `not_fits` 또는 `missing`/`error` → True |
| `both_axes_failed` | `contradicts` + `not_fits`일 때만 True |
| `both_axes_failed` | 인용 실패(`quote_verified=False`)인데 `fit="fits"` → False |

TTL(400일)·stale(300일) 동작은 `main()` 안에 있어 함수로 분리돼 있지 않다.
**Phase 6(LLM 호출 공통화)과 같은 방식으로 판정 로직을 함수로 빼낸 뒤 테스트한다.**
지금 단계에서는 위 순수 함수들만 덮는다.
