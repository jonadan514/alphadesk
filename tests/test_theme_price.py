"""주가 축 계산 규칙 (docs/TEST_PLAN.md 4장).

  - 가격을 확보한 기업이 5명 미만이거나 지수 수익률이 없으면 na (탈락 아님)
  - 소속 기업 수익률의 **중앙값**에서 지수 수익률을 뺀다 - 한 종목이 전체를 흔들지 않게
  - 초과수익 +8%p / +3%p / -3%p 경계
  - 거래대금 비율은 참고 수치일 뿐 화살표를 만들지 않는다 (표본 5개 미만이면 None)
"""
from __future__ import annotations

import pytest

from analyzers.theme_price import compute_price_signal

THRESHOLDS = {"strong_up": 0.08, "up": 0.03, "down": -0.03}


def members(n: int) -> list[dict]:
    return [{"ticker": f"T{i}"} for i in range(n)]


def returns(values: list[float | None]) -> dict[str, float | None]:
    return {f"T{i}": v for i, v in enumerate(values)}


def test_가격을_확보한_기업이_5명_미만이면_na():
    r = compute_price_signal(members(4), returns([0.1] * 4), 0.0, THRESHOLDS)
    assert r["arrow"] == "na" and r["median_ret"] is None and r["valid_count"] == 4


def test_수익률이_None인_기업은_세지_않는다():
    r = compute_price_signal(members(6), returns([0.1] * 4 + [None, None]), 0.0, THRESHOLDS)
    assert r["valid_count"] == 4 and r["arrow"] == "na"


def test_지수_수익률이_None이면_na():
    r = compute_price_signal(members(6), returns([0.1] * 6), None, THRESHOLDS)
    assert r["arrow"] == "na" and r["excess"] is None


@pytest.mark.parametrize("excess,arrow", [
    (0.08, "up2"),      # 경계 포함
    (0.05, "up1"),
    (0.03, "up1"),      # 경계 포함
    (0.00, "flat"),
    (-0.03, "down"),    # 경계 포함
    (-0.10, "down"),
])
def test_초과수익_경계에서_화살표가_갈린다(excess, arrow):
    index = 0.02
    r = compute_price_signal(members(5), returns([index + excess] * 5), index, THRESHOLDS)
    assert r["arrow"] == arrow
    assert r["excess"] == pytest.approx(excess)


def test_평균이_아니라_중앙값을_쓴다():
    """한 종목이 +200%여도 중앙값은 그대로다."""
    r = compute_price_signal(members(5), returns([0.01, 0.01, 0.01, 0.01, 2.00]), 0.0, THRESHOLDS)
    assert r["median_ret"] == pytest.approx(0.01)
    assert r["arrow"] == "flat"


def test_지수_수익률을_그대로_돌려준다():
    r = compute_price_signal(members(5), returns([0.0] * 5), 0.037, THRESHOLDS)
    assert r["index_ret"] == pytest.approx(0.037)


# ── 거래대금 참고 수치 ────────────────────────────────────────

def vols(values):
    return {f"T{i}": v for i, v in enumerate(values)}


def test_거래대금_비율은_중앙값이다():
    r = compute_price_signal(members(5), returns([0.0] * 5), 0.0, THRESHOLDS,
                             vols([0.5, 1.0, 1.5, 2.0, 9.0]))
    assert r["volume_ratio"] == pytest.approx(1.5)


def test_거래대금_표본이_5개_미만이면_None():
    r = compute_price_signal(members(5), returns([0.0] * 5), 0.0, THRESHOLDS,
                             vols([1.0, 1.0, 1.0, 1.0, None]))
    assert r["volume_ratio"] is None


def test_거래대금은_화살표에_영향을_주지_않는다():
    """네 번째 축이 아니라 참고 수치다(원칙 1)."""
    base = compute_price_signal(members(5), returns([0.0] * 5), 0.0, THRESHOLDS)
    with_vol = compute_price_signal(members(5), returns([0.0] * 5), 0.0, THRESHOLDS, vols([50.0] * 5))
    assert base["arrow"] == with_vol["arrow"] == "flat"


def test_na여도_거래대금_비율은_계산한다():
    r = compute_price_signal(members(5), returns([None] * 5), 0.0, THRESHOLDS, vols([2.0] * 5))
    assert r["arrow"] == "na" and r["volume_ratio"] == pytest.approx(2.0)
