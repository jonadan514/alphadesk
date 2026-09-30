"""실적 축 계산 규칙 (docs/TEST_PLAN.md 3장).

  - 분기가 부족하거나 분모가 0이면 데이터부족(None) - 탈락이 아니다 (원칙 4)
  - 시장 중앙값은 표본이 충분할 때만
  - 개선 비율 0.70 / 0.55 / 0.45 경계
  - 판정 가능 기업 5명 미만이거나 데이터부족이 40%를 넘으면 na
"""
from __future__ import annotations

import pandas as pd
import pytest

from analyzers.theme_earnings import (MIN_MEDIAN_SAMPLE, classify_company_earnings,
                                       compute_earn_signal, market_median_growth, yoy_growth)

THRESHOLDS = {"strong_up": 0.70, "up": 0.55, "down": 0.45}


def series(values: list[float]) -> pd.Series:
    """최신 분기가 0번째인 분기 매출 Series. 인덱스는 분기 말일(최신 -> 과거)."""
    idx = pd.date_range(end="2026-06-30", periods=len(values), freq="QE")[::-1]
    return pd.Series(values, index=idx)


def growing(g: float) -> pd.Series:
    """전년동기 100 -> 최근 100*(1+g)인 5분기 매출."""
    return series([100 * (1 + g), 100, 100, 100, 100])


# ── yoy_growth ────────────────────────────────────────────────

def test_전년동기_대비_성장률을_계산한다():
    assert yoy_growth(growing(0.25)) == pytest.approx(0.25)


def test_분기가_5개_미만이면_데이터부족이다():
    assert yoy_growth(series([110, 100, 100, 100])) is None


def test_None이면_데이터부족이다():
    assert yoy_growth(None) is None


def test_1년_전_매출이_0이면_데이터부족이다():
    assert yoy_growth(series([110, 100, 100, 100, 0])) is None


# ── 시장 중앙값 ───────────────────────────────────────────────

def test_표본이_20개_미만이면_중앙값을_내지_않는다():
    assert MIN_MEDIAN_SAMPLE == 20
    few = {f"T{i}": growing(0.1) for i in range(MIN_MEDIAN_SAMPLE - 1)}
    assert market_median_growth(few) is None


def test_표본이_충분하면_중앙값을_낸다():
    data = {f"T{i}": growing(i / 100) for i in range(MIN_MEDIAN_SAMPLE)}   # 0.00 ~ 0.19
    assert market_median_growth(data) == pytest.approx(0.095)


def test_중앙값_표본에서_데이터부족_기업은_뺀다():
    data = {f"T{i}": growing(0.1) for i in range(MIN_MEDIAN_SAMPLE)}
    data["NONE"] = None
    data["SHORT"] = series([110, 100])
    assert market_median_growth(data) == pytest.approx(0.1)


# ── 기업 판정 ─────────────────────────────────────────────────

def test_기준_성장률을_넘으면_improved():
    status, label = classify_company_earnings(growing(0.20), reference_growth=0.10)
    assert status == "improved" and label == "2026-Q2"


def test_기준_성장률과_같으면_not_improved():
    """'넘어야' 개선이다. 부동소수점 오차가 없도록 정확히 표현되는 값(0.25)을 쓴다."""
    assert classify_company_earnings(growing(0.25), reference_growth=0.25)[0] == "not_improved"
    assert classify_company_earnings(growing(0.30), reference_growth=0.25)[0] == "improved"


def test_계산_불가는_탈락이_아니라_insufficient():
    assert classify_company_earnings(series([100, 100]), 0.0) == ("insufficient", None)


# ── 테마 신호 ─────────────────────────────────────────────────

def members_and_revenue(improved: int, not_improved: int, insufficient: int = 0):
    """기준 성장률 0.10 기준으로 개선/미개선/데이터부족 기업을 만든다."""
    members, rev = [], {}
    for i in range(improved):
        members.append({"ticker": f"I{i}"}); rev[f"I{i}"] = growing(0.30)
    for i in range(not_improved):
        members.append({"ticker": f"N{i}"}); rev[f"N{i}"] = growing(0.00)
    for i in range(insufficient):
        members.append({"ticker": f"X{i}"}); rev[f"X{i}"] = None
    return members, rev


def test_판정_가능_기업이_5명_미만이면_na():
    members, rev = members_and_revenue(improved=3, not_improved=1)   # 4명
    r = compute_earn_signal(members, rev, THRESHOLDS, reference_growth=0.10)
    assert r["arrow"] == "na" and r["ratio"] is None


def test_데이터부족이_40퍼센트를_넘으면_na():
    members, rev = members_and_revenue(improved=6, not_improved=0, insufficient=5)   # 5/11 = 45%
    r = compute_earn_signal(members, rev, THRESHOLDS, reference_growth=0.10)
    assert r["arrow"] == "na"


def test_데이터부족이_정확히_40퍼센트면_계산한다():
    members, rev = members_and_revenue(improved=6, not_improved=0, insufficient=4)   # 4/10 = 40%
    assert compute_earn_signal(members, rev, THRESHOLDS, 0.10)["arrow"] != "na"


@pytest.mark.parametrize("improved,not_improved,arrow", [
    (7, 3, "up2"),     # 0.70 - 경계 포함
    (6, 4, "up1"),     # 0.60
    (11, 9, "up1"),    # 0.55 - 경계 포함
    (10, 10, "flat"),  # 0.50
    (9, 11, "down"),   # 0.45 - 경계 포함
    (2, 8, "down"),    # 0.20
])
def test_개선_비율_경계에서_화살표가_갈린다(improved, not_improved, arrow):
    members, rev = members_and_revenue(improved, not_improved)
    r = compute_earn_signal(members, rev, THRESHOLDS, reference_growth=0.10)
    assert r["arrow"] == arrow
    assert r["ratio"] == pytest.approx(improved / (improved + not_improved))


def test_기준_성장률이_None이면_0을_쓴다():
    members, rev = members_and_revenue(improved=6, not_improved=0)
    assert compute_earn_signal(members, rev, THRESHOLDS, reference_growth=None)["reference_growth"] == 0.0


def test_기준일은_가장_최근_분기다():
    members, rev = members_and_revenue(improved=5, not_improved=0)
    assert compute_earn_signal(members, rev, THRESHOLDS, 0.10)["as_of"] == "2026-Q2"


# ── 시장 중앙값의 표본 범위 (작업지시서 Phase 2) ───────────────
#
# "시장 중앙값"은 그 시장 유니버스 **전체**의 성장률 중앙값이어야 한다. 전에는 테마에
# 한 번이라도 소속된 기업만 표본이었다 - 그러면 소속 기업이 곧 표본이라 절반이 자동으로
# 기준 위에 놓이고(개선 비율이 0.5 근처로 쏠림), 테마가 몰려 있는 업종 성장이 기준선에
# 그대로 섞여 들어간다.

from analyzers.theme_earnings import reference_growth_for_market


def universe_revenue(n_high: int, n_low: int, *, market_prefix: str = "U"):
    """성장률 0.30인 기업 n_high개와 0.00인 기업 n_low개로 이뤄진 유니버스."""
    rev = {f"{market_prefix}H{i}": growing(0.30) for i in range(n_high)}
    rev.update({f"{market_prefix}L{i}": growing(0.00) for i in range(n_low)})
    return rev


def test_기준_성장률은_테마_소속이_아니라_시장_전체로_낸다():
    # 유니버스: 성장 기업 5 + 정체 기업 25 -> 중앙값 0.00
    # 테마 소속은 성장 기업 5곳뿐 - 소속만 표본으로 쓰면 중앙값이 0.30으로 나온다.
    universe = universe_revenue(5, 25)
    assert reference_growth_for_market(universe, "US") == pytest.approx(0.00)
    # 같은 데이터에서 성장 기업 20곳만 소속이라고 치면(표본 20개 충족) 소속 기준 중앙값은 0.30이다
    only_members = universe_revenue(20, 0)
    assert market_median_growth(only_members) == pytest.approx(0.30)


def test_소속이_성장_기업뿐이어도_시장_기준에서는_개선으로_판정된다():
    universe = universe_revenue(5, 25)
    ref = reference_growth_for_market(universe, "US")
    members = [{"ticker": f"UH{i}"} for i in range(5)]
    r = compute_earn_signal(members, universe, THRESHOLDS, reference_growth=ref)
    assert r["ratio"] == 1.0 and r["arrow"] == "up2"


def test_유니버스_표본이_20개_미만이면_None을_돌려준다():
    assert reference_growth_for_market(universe_revenue(5, 10), "US") is None


def test_데이터가_없는_종목은_표본에서_뺀다():
    universe = universe_revenue(10, 10)
    universe["NONE1"] = None
    universe["SHORT"] = series([1, 2])
    assert reference_growth_for_market(universe, "US") == pytest.approx(0.15)
