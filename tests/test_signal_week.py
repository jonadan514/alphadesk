"""정기 파이프라인이 채울 주(signal_week_monday) - 예약 실행이 월요일로 밀려도 끝난 주를 잡는지."""
from datetime import date

from src.db.theme_signals import signal_week_monday


def test_sunday_run_fills_that_week():
    # 정시(일요일 22:00 UTC) 실행
    assert signal_week_monday(date(2026, 10, 4)) == date(2026, 9, 28)


def test_monday_delayed_run_still_fills_previous_week():
    # 2026-10-05 00:22 UTC 실행 - 예전 규칙은 10-05(막 시작된 주)를 잡아 미국 뉴스 전부 0건이었다
    assert signal_week_monday(date(2026, 10, 5)) == date(2026, 9, 28)


def test_midweek_manual_run_uses_current_week():
    assert signal_week_monday(date(2026, 10, 7)) == date(2026, 10, 5)
    assert signal_week_monday(date(2026, 10, 6)) == date(2026, 10, 5)
