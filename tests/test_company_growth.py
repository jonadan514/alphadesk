"""기업 카드 성장 축 (docs/SPEC_watchlist_growth.md).

핵심은 세 가지다. (1) "최근 4개 회계기간"은 연도 간격이 정확히 3년이어야 한다
(중간에 공시 공백이 있으면 데이터부족). (2) 데이터부족(None)이 growth_tier에서
"역성장"으로 새지 않는다(원칙 4). (3) growth_tier 경계(0%, 10%)가 부동소수점
잡음으로 잘못 분류하지 않는다.
"""
from __future__ import annotations

import pytest

from src.analyzers.company_growth import (FLAT, GROWING, SHRINKING, growth_tier,
                                           operating_margin_direction, revenue_cagr,
                                           revenue_yoy)


def _p(year: int, revenue=None, operating_income=None) -> tuple[str, dict]:
    data = {}
    if revenue is not None:
        data["Total Revenue"] = revenue
    if operating_income is not None:
        data["Operating Income"] = operating_income
    return (f"{year}-12-31", data)


def _4y(revenues, op_incomes=(None, None, None, None)):
    """최신순 4개 연도(2026, 2025, 2024, 2023)."""
    years = (2026, 2025, 2024, 2023)
    return [_p(y, r, oi) for y, r, oi in zip(years, revenues, op_incomes)]


# ── 매출 3년 CAGR ─────────────────────────────────────────────

def test_3년_CAGR_계산():
    # 100 -> 133.1은 연 10% 성장 3년치
    periods = _4y(revenues=(133.1, 121.0, 110.0, 100.0))
    assert revenue_cagr(periods) == pytest.approx(0.10, abs=1e-6)


def test_회계기간_4개_미만이면_None():
    periods = _4y(revenues=(133.1, 121.0, 110.0, 100.0))[:3]
    assert revenue_cagr(periods) is None


def test_연도_간격이_3년이_아니면_None():
    """2026, 2025, 2024, 2022 - 최신 4개를 뽑아도 2026-2022는 4년 간격."""
    periods = [_p(2026, 133.1), _p(2025, 121.0), _p(2024, 110.0), _p(2022, 90.0)]
    assert revenue_cagr(periods) is None
    assert revenue_yoy(periods) is None


def test_매출_계정이_없으면_None():
    periods = [(f"{y}-12-31", {}) for y in (2026, 2025, 2024, 2023)]
    assert revenue_cagr(periods) is None


def test_매출이_0이하면_None():
    periods = _4y(revenues=(100.0, 121.0, 110.0, 0.0))
    assert revenue_cagr(periods) is None
    periods_neg = _4y(revenues=(-50.0, 121.0, 110.0, 100.0))
    assert revenue_cagr(periods_neg) is None


def test_정렬되지_않은_입력도_내부에서_정렬한다():
    """호출부가 순서를 뒤섞어 넘겨도 모듈이 최신순으로 다시 정렬해야 한다."""
    periods = _4y(revenues=(133.1, 121.0, 110.0, 100.0))
    shuffled = [periods[2], periods[0], periods[3], periods[1]]
    assert revenue_cagr(shuffled) == pytest.approx(0.10, abs=1e-6)


def test_Operating_Revenue_로도_계산된다():
    """Total Revenue가 없는 소수 종목 대비 - Operating Revenue를 다음 순서로 쓴다."""
    periods = [
        ("2026-12-31", {"Operating Revenue": 133.1}),
        ("2025-12-31", {"Operating Revenue": 121.0}),
        ("2024-12-31", {"Operating Revenue": 110.0}),
        ("2023-12-31", {"Operating Revenue": 100.0}),
    ]
    assert revenue_cagr(periods) == pytest.approx(0.10, abs=1e-6)


# ── 최근 1년 성장률 ────────────────────────────────────────────

def test_최근_1년_성장률():
    periods = _4y(revenues=(133.1, 121.0, 110.0, 100.0))
    assert revenue_yoy(periods) == pytest.approx(133.1 / 121.0 - 1)


def test_최근_1년도_3년_창이_계산_불가면_None():
    """3년 CAGR이 안 되면(연도 간격 불일치) 최근 1년도 같이 None -
    같은 스냅샷에서 나온 두 값이 서로 다른 신뢰 기준을 쓰면 안 된다."""
    periods = [_p(2026, 133.1), _p(2025, 121.0), _p(2024, 110.0), _p(2022, 90.0)]
    assert revenue_yoy(periods) is None


# ── 영업이익률 방향 ────────────────────────────────────────────

def test_영업이익률_개선():
    # 최신: 100/1000=10% / 3년전: 50/1000=5% -> 개선
    periods = _4y(revenues=(1000.0, 900.0, 950.0, 1000.0),
                  op_incomes=(100.0, 90.0, 70.0, 50.0))
    assert operating_margin_direction(periods) == "개선"


def test_영업이익률_악화():
    periods = _4y(revenues=(1000.0, 900.0, 950.0, 1000.0),
                  op_incomes=(30.0, 90.0, 70.0, 50.0))
    assert operating_margin_direction(periods) == "악화"


def test_영업이익_계정이_없어도_매출_CAGR은_그대로_계산된다():
    """서로 다른 계정에 의존 - 영업이익이 없다고 매출 CAGR까지 막지 않는다."""
    periods = _4y(revenues=(133.1, 121.0, 110.0, 100.0))   # op_income 전부 None
    assert revenue_cagr(periods) == pytest.approx(0.10, abs=1e-6)
    assert operating_margin_direction(periods) is None


# ── growth_tier: 절대 기준 + 데이터부족 격리 ───────────────────

def test_역성장_경계():
    assert growth_tier(-0.01) == SHRINKING
    assert growth_tier(-0.132) == SHRINKING


def test_정체_경계():
    assert growth_tier(0.0) == FLAT
    assert growth_tier(0.05) == FLAT


def test_성장_경계():
    assert growth_tier(0.10) == GROWING
    assert growth_tier(0.20) == GROWING


def test_경계값_정확히_0퍼센트는_정체():
    assert growth_tier(0.0) == FLAT
    assert growth_tier(-0.001) == SHRINKING   # 진짜 음의 성장은 역성장
    # 아홉째 자리 반올림보다 작은 잡음은 0으로 뭉개진다(의도적 - 실제 계산값이
    # 아니라 부동소수점 표현 오차 수준이라 "역성장"이라 부를 근거가 못 된다).
    assert growth_tier(-1e-12) == FLAT


def test_경계값_정확히_10퍼센트는_성장_부동소수점_잡음_방어():
    """실측 사례: 100 -> 133.1(연 10%) 역산 시 0.10000000000000009나
    0.09999999999999964처럼 부동소수점 잡음이 낄 수 있다 - 둘 다 성장으로 분류돼야 한다."""
    assert growth_tier(0.10000000000000009) == GROWING
    assert growth_tier(0.09999999999999964) == GROWING   # 반올림 방어가 없으면 정체로 잘못 분류됨
    # revenue_cagr()가 실제로 내는 값으로도 확인
    periods = _4y(revenues=(133.1, 121.0, 110.0, 100.0))
    assert growth_tier(revenue_cagr(periods)) == GROWING


def test_데이터부족은_역성장으로_새지_않는다():
    """원칙 4 - growth_tier(None)은 None이지 SHRINKING이 아니다."""
    assert growth_tier(None) is None
