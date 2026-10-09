"""최근 분기 매출 전년동기 대비 (company_growth.quarterly_revenue_yoy) - 3년 판정 옆에 따로 보여 주는 값."""
import pandas as pd

from src.analyzers.company_growth import quarterly_revenue_yoy


def _df(cols):
    """cols: [(분기말, 매출)] 최신순."""
    return pd.DataFrame({pd.Timestamp(d): pd.Series({"Total Revenue": r, "Operating Income": 1.0}) for d, r in cols})


def test_samsung_like_boom_is_growing_even_if_3y_is_flat():
    # 2026-10-09 실제 값(조 원): 2026Q2 171.50, 2025Q2 74.57 -> +130%
    r = quarterly_revenue_yoy(_df([("2026-06-30", 171.50), ("2026-03-31", 133.87), ("2025-12-31", 93.84),
                                   ("2025-09-30", 86.06), ("2025-06-30", 74.57)]))
    assert r["tier"] == "성장" and r["quarter"] == "2026-Q2"
    assert abs(r["yoy"] - (171.50 / 74.57 - 1)) < 1e-9


def test_tiers_use_same_boundaries_as_3y():
    assert quarterly_revenue_yoy(_df([("2026-06-30", 105), ("2025-06-30", 100)]))["tier"] == "정체"
    assert quarterly_revenue_yoy(_df([("2026-06-30", 110), ("2025-06-30", 100)]))["tier"] == "성장"
    assert quarterly_revenue_yoy(_df([("2026-06-30", 95), ("2025-06-30", 100)]))["tier"] == "역성장"


def test_non_calendar_fiscal_quarter_matches_year_ago():
    # 마이크론처럼 5월 말 분기 - 2026-05-31 vs 2025-05-31
    r = quarterly_revenue_yoy(_df([("2026-05-31", 41456), ("2026-02-28", 23860), ("2025-11-30", 13643),
                                   ("2025-08-31", 11315), ("2025-05-31", 9301)]))
    assert r["tier"] == "성장" and abs(r["yoy"] - (41456 / 9301 - 1)) < 1e-9


def test_insufficient_is_none_not_shrinking():
    assert quarterly_revenue_yoy(None) is None
    assert quarterly_revenue_yoy(_df([("2026-06-30", 100), ("2026-03-31", 90)])) is None   # 1년 전 분기 없음
    assert quarterly_revenue_yoy(_df([("2026-06-30", 100), ("2025-06-30", 0)])) is None    # 기준 매출 0
