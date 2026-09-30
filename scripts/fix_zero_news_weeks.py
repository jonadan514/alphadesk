"""수집 실패로 0이 저장된 주를 NULL로 되돌린다 (일회성 정리, 멱등적).

2026-09-28 구글 뉴스가 Actions IP를 막아 전 테마가 0건으로 수집됐고, 그 0이
theme_signals.news_count에 **정수 0으로** 들어갔다. 기준선을 만드는
get_prior_news_counts()는 `news_count IS NOT NULL`인 주만 거르기 때문에 0은
그대로 섞인다 - 기준선은 직전 8주 중앙값이라 0이 5주쯤 쌓이면 중앙값이 0이 되고,
그때부터 뉴스 축이 영구히 "na"로 죽는다.

collect_theme_news.py는 2026-09-30부터 "전 테마 0건이면 NULL로 저장"하도록
고쳤지만, 이미 들어간 행은 이 스크립트로 따로 치워야 한다.

**한 테마만 0건인 주는 건드리지 않는다.** 그건 실제로 그 주에 뉴스가 없었다는
정보다. 같은 (market, week_start)에서 **모든** 테마가 0일 때만 수집 실패로 보고
NULL로 바꾼다 - collect_theme_news.is_collection_failure()와 같은 기준이다.

Usage:
  python scripts/fix_zero_news_weeks.py --dry-run   # 무엇이 바뀌는지만 본다
  python scripts/fix_zero_news_weeks.py             # 실제로 고친다
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db


def _log(msg: str) -> None:
    print(f"[fix-zero-news] {msg}", flush=True)


def find_failed_weeks(conn) -> list[tuple[str, str, int]]:
    """(market, week_start, 테마수) - 그 주 모든 테마가 news_count=0인 경우만."""
    rows = conn.execute(
        "SELECT market, week_start, theme_id, news_count FROM theme_signals "
        "WHERE news_count IS NOT NULL"
    ).fetchall()

    by_week: dict[tuple[str, str], list[int]] = defaultdict(list)
    for market, week_start, _theme_id, news_count in rows:
        by_week[(str(market), str(week_start))].append(int(news_count))

    failed = []
    for (market, week_start), counts in sorted(by_week.items()):
        if counts and all(c == 0 for c in counts):
            failed.append((market, week_start, len(counts)))
    return failed


def clear_week(conn, market: str, week_start: str) -> None:
    """그 주의 뉴스 축만 비운다. 실적·주가 축은 건드리지 않는다
    (theme_signals 한 행을 세 축이 나눠 쓰고 있다)."""
    conn.execute(
        "UPDATE theme_signals SET news_count = NULL, news_ratio = NULL, news_arrow = 'na' "
        "WHERE market = ? AND week_start = ?",
        (market, week_start),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="바꾸지 않고 대상만 출력")
    args = ap.parse_args()

    conn = get_db()
    failed = find_failed_weeks(conn)

    if not failed:
        _log("전 테마가 0건인 주가 없다 - 고칠 것 없음")
        conn.close()
        return 0

    _log(f"수집 실패로 판단되는 주 {len(failed)}개:")
    for market, week_start, n in failed:
        _log(f"  {market} {week_start} - 테마 {n}개 전부 0건")

    if args.dry_run:
        _log("--dry-run 이라 실제로 바꾸지 않았다")
        conn.close()
        return 0

    for market, week_start, _n in failed:
        clear_week(conn, market, week_start)
    conn.commit()
    conn.close()
    _log(f"완료 - {len(failed)}개 주의 news_count를 NULL로 되돌렸다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
