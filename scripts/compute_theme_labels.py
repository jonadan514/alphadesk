"""Phase A-6/B-4: 세 축이 다 채워진 뒤 조합 라벨을 부여.

SPEC: docs/radar/SPEC_phase_a_signals.md §5
뉴스(22:00 UTC)/실적(22:15)/주가(22:30) 축 계산이 전부 끝난 뒤 돌아야 한다 -
워크플로 크론을 22:45로 둬서 순서를 보장한다.
Phase B에서 한국도 같은 규칙으로 처리한다(라벨 규칙 자체는 시장 무관 -
세 축 화살표만 보고 판정하므로 US/KR에 그대로 적용).

Usage:
  python scripts/compute_theme_labels.py
"""
from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--week-start", default=None,
                         help="기준 주 월요일(YYYY-MM-DD). 비우면 오늘이 속한 주 - "
                              "주 초에 수동 실행할 때 세 축이 아직 안 채워진 새 주를 "
                              "잡지 않도록 명시적으로 지정하기 위한 옵션.")
    args = parser.parse_args()

    conn = get_db()
    ensure_schema(conn)

    week_start = args.week_start or _current_week_monday(date.today()).isoformat()

    total_rows = 0
    total_labeled = 0
    for market in ("US", "KR"):
        rows = get_week_signals(conn, market, week_start)
        if not rows:
            _log(f"{market}: {week_start}에 해당하는 theme_signals 행이 없음 - 건너뜀")
            continue

        labeled = 0
        for row in rows:
            label = compute_label(row["news_arrow"], row["earn_arrow"], row["price_arrow"])
            update_theme_label(conn, row["theme_id"], market, week_start, label)
            if label:
                labeled += 1
                _log(f"{row['theme_id']}({market}): "
                     f"{row['news_arrow']}/{row['earn_arrow']}/{row['price_arrow']} -> {label}")
        conn.commit()
        _log(f"{market}: {len(rows)}개 테마 중 {labeled}개 라벨 부여")
        total_rows += len(rows)
        total_labeled += labeled

    if total_rows == 0:
        _log("어느 시장에도 해당 주 행이 없음 - 뉴스/실적/주가 축을 먼저 돌릴 것")
        conn.close()
        sys.exit(1)

    conn.close()
    _log(f"전체 완료 - {total_rows}개 중 {total_labeled}개 라벨 부여")


if __name__ == "__main__":
    main()
