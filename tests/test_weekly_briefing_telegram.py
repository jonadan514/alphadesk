"""주간 브리핑 텔레그램 본문 (2026-10-05 정리분) - 건수·이스케이프·라벨 없음 안내."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "generate_weekly_briefing", Path(__file__).resolve().parent.parent / "scripts" / "generate_weekly_briefing.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


def _briefing(**over):
    b = {"week": "2026-10-12", "us": {"index_chg_1w": 1.2}, "kr": {"index_chg_1w": -0.5},
         "macro": {"us10y": {"value": 4.1234, "chg_1w": 0.0812}, "usdkrw": {"value": 1386.4, "chg_1w": -12.3}},
         "watchlist": {"total": 275, "added": [{"market": "KR", "symbol": str(i), "name": f"종목{i}"} for i in range(10)],
                       "removed": [], "added_count": 27, "removed_count": 0, "has_prev": True},
         "sentiment_heating": [], "theme_labels": {"week_start": "2026-10-05", "new_labels": [],
                                                   "label_counts": {"US": 0, "KR": 0}}}
    b.update(over)
    return b


def test_counts_use_full_total_not_truncated_list():
    text = g.build_telegram_summary(_briefing())
    assert "신규 27" in text and "외 24개" in text


def test_names_are_html_escaped():
    wl = {"total": 1, "added": [{"market": "KR", "symbol": "383220", "name": "F&F"}], "removed": [],
          "added_count": 1, "removed_count": 0, "has_prev": True}
    text = g.build_telegram_summary(_briefing(watchlist=wl))
    assert "F&amp;F" in text and "F&F" not in text


def test_theme_radar_line_always_present():
    assert "아직 라벨 없음" in g.build_telegram_summary(_briefing())
    assert "테마 신호 데이터 없음" in g.build_telegram_summary(_briefing(theme_labels={}))


def test_macro_line_and_no_gpt():
    text = g.build_telegram_summary(_briefing(gpt_comment="지수가 3% 올랐다"))
    assert "미 10년물 4.12% (+0.08%p)" in text and "원/달러 1,386원 (-12원)" in text
    assert "3% 올랐다" not in text          # GPT 총평은 웹에만
    assert "금리·환율" not in g.build_telegram_summary(_briefing(macro=None))


def test_no_double_blank_lines():
    text = g.build_telegram_summary(_briefing(us={}, kr={}, macro=None))
    assert "\n\n\n" not in text
