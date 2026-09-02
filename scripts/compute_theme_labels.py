"""Phase A-6: 세 축이 다 채워진 뒤 조합 라벨을 부여.

SPEC: docs/radar/SPEC_phase_a_signals.md §5
뉴스(22:00 UTC)/실적(22:15)/주가(22:30) 축 계산이 전부 끝난 뒤 돌아야 한다 -
워크플로 크론을 22:45로 둬서 순서를 보장한다.

Usage:
  python scripts/compute_theme_labels.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.theme_signals import ensure_schema, get_week_signals, update_theme_label
from analyzers.theme_labels import compute_label


def _log(msg: str) -> None:
    print(f"[label] {msg}")


def _current_week_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def main() -> None:
    conn = get_db()
    ensure_schema(conn)

    week_start = _current_week_monday(date.today()).isoformat()
    rows = get_week_signals(conn, "US", week_start)
    if not rows:
        _log(f"{week_start}에 해당하는 theme_signals 행이 없음 - 뉴스/실적/주가 축을 먼저 돌릴 것")
        sys.exit(1)

    labeled = 0
    for row in rows:
        label = compute_label(row["news_arrow"], row["earn_arrow"], row["price_arrow"])
        update_theme_label(conn, row["theme_id"], "US", week_start, label)
        if label:
            labeled += 1
            _log(f"{row['theme_id']}: {row['news_arrow']}/{row['earn_arrow']}/{row['price_arrow']} -> {label}")
    conn.commit()

    conn.close()
    _log(f"완료 - {len(rows)}개 테마 중 {labeled}개 라벨 부여")


if __name__ == "__main__":
    main()
