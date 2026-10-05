"""분기 영업이익률 전년동기 비교 (company_growth.quarterly_margin_change)."""
import pandas as pd

from src.analyzers.company_growth import quarterly_margin_change


def _df(cols):
    """cols: [(분기말, 매출, 영업이익)] 최신순."""
    return pd.DataFrame({pd.Timestamp(d): pd.Series({"Total Revenue": r, "Operating Income": o}) for d, r, o in cols})


def test_improved_against_same_quarter_last_year():
    df = _df([("2026-06-30", 100, 15), ("2026-03-31", 90, 9), ("2025-12-31", 95, 9),
              ("2025-09-30", 80, 8), ("2025-06-30", 80, 8)])
    r = quarterly_margin_change(df)
    assert r["status"] == "개선" and r["quarter"] == "2026-Q2"
    assert abs(r["now"] - 0.15) < 1e-9 and abs(r["year_ago"] - 0.10) < 1e-9 and abs(r["change"] - 0.05) < 1e-9


def test_small_change_is_flat_and_loss_narrowing_is_improved():
    flat = _df([("2026-06-30", 100, 10.5), ("2025-06-30", 100, 10)])
    assert quarterly_margin_change(flat)["status"] == "유지"
    loss = _df([("2026-06-30", 100, -2), ("2025-06-30", 100, -8)])
    assert quarterly_margin_change(loss)["status"] == "개선"


def test_insufficient_cases_are_none():
    assert quarterly_margin_change(None) is None
    assert quarterly_margin_change(_df([("2026-06-30", 100, 10), ("2026-03-31", 100, 9)])) is None   # 1년 전 분기 없음
    assert quarterly_margin_change(_df([("2026-06-30", 0, 1), ("2025-06-30", 100, 9)])) is None      # 매출 0
    nan = _df([("2026-06-30", 100, float("nan")), ("2025-06-30", 100, 9)])
    assert quarterly_margin_change(nan) is None
