"""분기 재무 백필 대상 선정 - 최신 분기가 이미 있는 종목은 건너뛴다."""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from backfill_quarterly_financials import FRESH_DAYS, select_targets  # noqa: E402


def test_skips_recent_quarter_and_keeps_missing_or_old():
    today = date(2026, 10, 9)
    latest = {"AAA": "2026-09-30", "BBB": "2026-06-30", "CCC": "2026-07-26"}
    todo, skipped = select_targets(["AAA", "BBB", "CCC", "NEW"], latest, today)
    # 9/30 분기 있음 -> 건너뜀 / 6/30이 마지막 -> 9월 분기 나올 때라 조회 / 캐시 없음 -> 조회
    assert "AAA" not in todo and "BBB" in todo and "NEW" in todo
    # 7/26 말일(비달력 회계연도): 88일 안이라 다음 분기는 아직 안 끝났다
    assert "CCC" not in todo
    assert skipped == 2


def test_boundary_and_force():
    today = date(2026, 10, 9)
    edge = date.fromordinal(today.toordinal() - FRESH_DAYS).isoformat()
    todo, _ = select_targets(["X"], {"X": edge}, today)
    assert todo == []          # 정확히 경계일은 아직 최신으로 본다
    todo, skipped = select_targets(["X"], {"X": "2026-09-30"}, today, force=True)
    assert todo == ["X"] and skipped == 0
