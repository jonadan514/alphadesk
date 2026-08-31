"""테마 매핑 결과를 사람이 검토할 수 있는 형태로 출력한다 (SPEC §7).

읽기 전용 — OpenAI를 호출하지 않는다. 최신 run_id(또는 지정한 run_id)의
theme_members를 CSV 형태로 표준출력에 찍는다.

Usage:
  python scripts/export_theme_mapping_review.py                 # 최신 run
  python scripts/export_theme_mapping_review.py --run-id 20260830...
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None, help="비우면 가장 최근 run")
    args = parser.parse_args()

    conn = get_db()

    run_id = args.run_id
    if not run_id:
        row = conn.execute("SELECT run_id FROM mapping_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        if not row:
            print("mapping_runs에 기록이 없습니다.")
            sys.exit(1)
        run_id = row[0]

    print(f"# run_id = {run_id}\n", file=sys.stderr)

    rows = conn.execute(
        """
        SELECT theme_id, ticker, market, stage, linkage, confidence, flagged, evidence
        FROM theme_members
        WHERE run_id = ?
        ORDER BY theme_id, ticker
        """,
        (run_id,),
    ).fetchall()

    writer = csv.writer(sys.stdout)
    writer.writerow(["theme_id", "ticker", "market", "stage", "linkage", "confidence", "flagged", "evidence"])
    for r in rows:
        writer.writerow(list(r))

    print(f"\n# 총 {len(rows)}건", file=sys.stderr)
    conn.close()


if __name__ == "__main__":
    main()
