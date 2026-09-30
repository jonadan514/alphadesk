"""기업 카드 성장 축 (docs/SPEC_watchlist_growth.md).

매출 3년 CAGR + 최근 1년 성장률 + 영업이익률 방향을 계산한다. company_valuation.py와
같은 성격의 순수 함수 모듈 - 네트워크·DB 접근 없음, 이미 조회된 데이터만 받는다.

## 밸류와 다른 점 - 절대 기준을 쓴다

PSR은 "비싼지 싼지"에 절대 기준이 없어 같은 시장 후보 안에서 순위로 3등분한다
(company_valuation.theme_valuation_tiers). 성장은 다르다. 실측(워치리스트 후보
KR 121 / US 154, SPEC 2장)으로 86-93%가 이미 양의 성장 중인 것을 확인했다 -
순위로 3등분하면 +3%로 성장 중인 기업에 "역성장" 라벨이 붙는다. 0%라는 절대
기준선 자체가 "매출이 줄었다"는 사실을 나타내므로 절대 기준(growth_tier)을 쓴다.

## 입력 계약

periods는 fundamentals_cache의 연차 손익계산서를 [(period_end: str, data: dict), ...]
형태로 담은 리스트다. 호출부가 이미 정렬해서 넘겨도 이 모듈이 내부에서 다시 한번
최신순으로 정렬한다 - company_valuation.py가 select_quarters() 리스트 하나만으로
자기 계산을 완결짓는 것과 같은 원칙: 호출부의 정렬 실수가 조용히 틀린 CAGR을
만들면 안 된다.

## 데이터부족 (원칙 4)

  - 회계기간이 4개 미만이면 계산 불가.
  - 최근 4개 시점의 연도 간격이 정확히 3년이 아니면(공시 공백 등) 계산하지 않는다 -
    "3년 CAGR"이라는 말과 다른 값이 조용히 나오는 것을 막는다
    (company_valuation._last_4q_sum의 "연속 4분기"와 같은 엄격함). SPEC 2장 실측으로
    이 규칙의 탈락 비용은 0종목이었다 - 느슨하게 할 이유가 없다.
  - 매출 계정이 없거나, 최신/기준 시점 매출이 0 이하면 None(성장률이 정의되지 않는다).
  - 영업이익률 방향은 영업이익 계정이 없으면 None - 매출 CAGR은 이 값과 무관하게
    그대로 계산된다(서로 다른 계정에 의존하므로 하나가 없다고 다른 하나까지
    막을 이유가 없다).
  - growth_tier(None)은 None이다 - 데이터부족을 "역성장"으로 묶지 않는다.
"""
from __future__ import annotations

GROWING = "성장"
FLAT = "정체"
SHRINKING = "역성장"

# 실측(SPEC 2장)에서 이 순서로 99% 성공. Total Revenue가 없는 소수 종목에 대비해
# Operating Revenue를 다음 순서로 둔다.
REVENUE_KEYS = ("Total Revenue", "Operating Revenue")
OPERATING_INCOME_KEYS = ("Operating Income", "Total Operating Income As Reported", "EBIT")

YEARS = 3   # 3년 CAGR - 최근 4개 회계연도(연도 간격 정확히 3년)가 필요하다

# growth_tier 경계값. SPEC 4-3 - 실측 분포에서 고른 시작점이다(임의값이 아니다:
# 0%는 "매출이 줄었다"는 사실의 경계, 10%는 KR 47%/US 35%가 "성장"이 되는 지점).
# MASTER_PLAN §9 "임의로 정한 숫자" 목록에 추가할 것.
FLAT_UPPER = 0.10


def _sorted_periods(periods: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """최신순(내림차순) 정렬. ISO 날짜 문자열이라 문자열 정렬이 곧 날짜 정렬."""
    return sorted(periods, key=lambda p: p[0], reverse=True)


def _pick(data: dict, keys: tuple[str, ...]) -> float | None:
    for k in keys:
        v = data.get(k)
        if v is not None:
            return float(v)
    return None


def _window(periods: list[tuple[str, dict]]) -> list[tuple[str, dict]] | None:
    """최근 YEARS+1개 회계기간을 뽑는다. 개수가 모자라거나 연도 간격이 정확히
    YEARS년이 아니면 None(계산 불가 - 위 모듈 설명의 엄격한 규칙)."""
    ordered = _sorted_periods(periods)
    if len(ordered) < YEARS + 1:
        return None
    window = ordered[: YEARS + 1]
    try:
        years = [int(p[0][:4]) for p in window]
    except (ValueError, IndexError, TypeError):
        return None
    if years[0] - years[-1] != YEARS:
        return None
    return window


def revenue_cagr(periods: list[tuple[str, dict]]) -> float | None:
    """매출 3년 CAGR = (최신매출 / 3년전매출) ** (1/3) - 1 (SPEC 4-2)."""
    window = _window(periods)
    if window is None:
        return None
    recent = _pick(window[0][1], REVENUE_KEYS)
    base = _pick(window[-1][1], REVENUE_KEYS)
    if recent is None or base is None or recent <= 0 or base <= 0:
        return None
    return (recent / base) ** (1 / YEARS) - 1


def revenue_yoy(periods: list[tuple[str, dict]]) -> float | None:
    """최근 1년 매출 성장률 = 최신매출 / 직전연도매출 - 1 (SPEC 4-2).

    _window()과 같은 4개 시점 창을 쓴다 - 3년 CAGR이 계산 불가면(연도 간격이
    안 맞는 등) 최근 1년도 같이 계산하지 않는다. 같은 재무제표 스냅샷에서 나온
    두 수치가 서로 다른 신뢰 기준을 쓰면 화면에서 "3년은 데이터부족인데 1년은
    나온다"는 앞뒤 안 맞는 상태가 된다.
    """
    window = _window(periods)
    if window is None:
        return None
    recent = _pick(window[0][1], REVENUE_KEYS)
    prior = _pick(window[1][1], REVENUE_KEYS)
    if recent is None or prior is None or recent <= 0 or prior <= 0:
        return None
    return recent / prior - 1


def operating_margin_direction(periods: list[tuple[str, dict]]) -> str | None:
    """영업이익률이 3년 전보다 개선됐는지 ("개선"|"악화"). 계산 불가면 None."""
    window = _window(periods)
    if window is None:
        return None
    recent_rev = _pick(window[0][1], REVENUE_KEYS)
    base_rev = _pick(window[-1][1], REVENUE_KEYS)
    recent_oi = _pick(window[0][1], OPERATING_INCOME_KEYS)
    base_oi = _pick(window[-1][1], OPERATING_INCOME_KEYS)
    if None in (recent_rev, base_rev, recent_oi, base_oi):
        return None
    if recent_rev <= 0 or base_rev <= 0:
        return None
    return "개선" if (recent_oi / recent_rev) > (base_oi / base_rev) else "악화"


def growth_tier(cagr: float | None) -> str | None:
    """절대 기준 3분류 (SPEC 4-3) - 순위가 아니라 고정된 경계값과 비교한다.
    데이터부족(None)은 그대로 None으로 돌려준다 - "역성장"으로 묶지 않는다(원칙 4).

    소수점 경계 비교: cagr은 세제곱근(**（1/3))을 거친 값이라 부동소수점 잡음이
    낀다(예: 수학적으로 정확히 10%인 입력이 0.10000000000000009나
    0.09999999999999964로 계산될 수 있다 - 이진 부동소수점이 0.1을 정확히
    표현하지 못하는 것과 같은 종류의 문제, company_change_signals.py의
    "0.19999999999999996 사건"과 동일 계열). 여기서는 값을 소수 아홉째 자리에서
    반올림해 그 잡음을 지운 뒤 경계와 비교한다 - 성장률을 화면에 소수 첫째 자리로
    보여주는 것을 감안하면 아홉째 자리 반올림이 실제 판단을 바꿀 일은 없다.
    """
    if cagr is None:
        return None
    rounded = round(cagr, 9)
    if rounded < 0:
        return SHRINKING
    if rounded < FLAT_UPPER:
        return FLAT
    return GROWING
