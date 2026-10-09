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


# ---- 최근 4개 분기 합 대 직전 4개 분기 합 (company_growth.ttm_revenue_yoy) ----
from src.analyzers.company_growth import ttm_revenue_yoy  # noqa: E402


def _q(rows):
    """rows: [(연도, 분기, 매출)]"""
    return [{"fiscal_year": y, "fiscal_quarter": q, "revenue": r} for y, q, r in rows]


def test_ttm_needs_eight_consecutive_quarters():
    eight = _q([(2026, 2, 171.5), (2026, 1, 133.9), (2025, 4, 93.8), (2025, 3, 86.1),
                (2025, 2, 74.6), (2025, 1, 79.1), (2024, 4, 75.8), (2024, 3, 79.1)])
    r = ttm_revenue_yoy(eight)
    now, ago = 171.5 + 133.9 + 93.8 + 86.1, 74.6 + 79.1 + 75.8 + 79.1
    assert abs(r["yoy"] - (now / ago - 1)) < 1e-9 and r["tier"] == "성장" and r["quarter"] == "2026-Q2"
    assert ttm_revenue_yoy(eight[:7]) is None                      # 7개뿐
    gap = [x for x in eight if (x["fiscal_year"], x["fiscal_quarter"]) != (2025, 1)]
    assert ttm_revenue_yoy(gap + _q([(2024, 2, 70)])) is None      # 중간이 빠짐 - 있는 것만으로 합 내지 않음


def test_ttm_crosses_year_boundary_and_handles_missing_value():
    rows = _q([(2026, 1, 10), (2025, 4, 10), (2025, 3, 10), (2025, 2, 10),
               (2025, 1, 10), (2024, 4, 10), (2024, 3, 10), (2024, 2, 10)])
    assert ttm_revenue_yoy(rows)["tier"] == "정체"   # 0%
    rows[5]["revenue"] = None
    assert ttm_revenue_yoy(rows) is None
    assert ttm_revenue_yoy([]) is None
