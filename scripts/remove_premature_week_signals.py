"""아직 끝나지 않은 주에 미리 만들어진 theme_signals 행을 지운다 (일회성 정리, 멱등).

2026-10-05 정기 뉴스 수집이 2시간 넘게 밀려 월요일 00:22(UTC)에 시작했고, '오늘이 속한 주'
규칙 때문에 막 시작된 2026-10-05 주를 채웠다(미국은 전 테마 0건 -> NULL, 한국은 몇 시간치).
화면은 MAX(week_start)를 '이번 주'로 읽어서, 뉴스만 든 이 행 때문에 레이더가 라벨·실적·주가 없는
주를 보여 준다. 규칙은 signal_week_monday()로 고쳤고, 이미 생긴 행은 이 스크립트로 치운다.

안전장치:
  - 지정한 주가 아직 진행 중일 때만(정기 파이프라인이 채울 주보다 뒤) 지운다.
  - 뉴스 축만 채워진 행(실적·주가·라벨이 전부 비어 있음)만 지운다.
  - theme_news(기사 원본)는 지우지 않는다 - 그 주의 실제 기사라 주말 정기 수집 때 그대로 이어 쓴다.

Usage:
  python scripts/remove_premature_week_signals.py --week 2026-10-05 --dry-run
  python scripts/remove_premature_week_signals.py --week 2026-10-05
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.theme_signals import signal_week_monday

NEWS_ONLY = "earn_arrow IS NULL AND price_arrow IS NULL AND label IS NULL"


def _log(msg: str) -> None:
    print(f"[premature-week] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", required=True, help="지울 주의 월요일 (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    target = signal_week_monday(date.today()).isoformat()
    if args.week <= target:
        _log(f"{args.week}은 이미 끝났거나 정기 파이프라인이 채울 주({target})다 - 지우지 않는다")
        return 1

    conn = get_db()
    rows = conn.execute(
        "SELECT market, theme_id, news_count, earn_arrow, price_arrow, label FROM theme_signals "
        "WHERE week_start = ? ORDER BY market, theme_id", (args.week,)).fetchall()
    keep = [r for r in rows if any(v is not None for v in r[3:])]
    drop = [r for r in rows if not any(v is not None for v in r[3:])]
    for m, tid, cnt, *_ in drop:
        _log(f"  삭제 대상 {m} {tid} news_count={cnt}")
    for m, tid, _cnt, e, p, lab in keep:
        _log(f"  유지(다른 축 있음) {m} {tid} earn={e} price={p} label={lab}")
    _log(f"{args.week}: 행 {len(rows)}개 중 삭제 {len(drop)} / 유지 {len(keep)}")

    if args.dry_run:
        _log("dry-run - 바꾸지 않음")
        return 0
    conn.execute(f"DELETE FROM theme_signals WHERE week_start = ? AND {NEWS_ONLY}", (args.week,))
    conn.commit()
    left = conn.execute("SELECT COUNT(*) FROM theme_signals WHERE week_start = ?", (args.week,)).fetchone()[0]
    _log(f"삭제 완료 - 남은 행 {left}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
