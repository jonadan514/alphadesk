"""테마 매핑 결과 승인 (SPEC §7).

export_theme_mapping_review.py로 뽑은 CSV를 사람이 검토한 뒤, 문제없으면
approved=1로 확정한다. 제외하기로 한 것만 --exclude로 넘기면 나머지는 전부
승인된다. 제외된 행은 삭제되지 않고 approved=0으로 남는다(이력 보존).

Usage:
  python scripts/approve_theme_mapping.py                                    # 최신 run 전체 승인
  python scripts/approve_theme_mapping.py --run-id 20260901012050-53eebe
  python scripts/approve_theme_mapping.py --exclude nuclear_smr:034730 shipbuilding:BA
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db
from src.db.theme_mapping import approve_theme_members


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None, help="비우면 가장 최근 run")
    parser.add_argument("--exclude", nargs="*", default=[], metavar="THEME_ID:TICKER",
                         help="검토 중 제외하기로 한 항목 (예: nuclear_smr:034730)")
    args = parser.parse_args()

    conn = get_db()

    run_id = args.run_id
    if not run_id:
        row = conn.execute("SELECT run_id FROM mapping_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        if not row:
            print("mapping_runs에 기록이 없습니다.")
            sys.exit(1)
        run_id = row[0]

    exclude: set[tuple[str, str]] = set()
    for item in args.exclude:
        if ":" not in item:
            print(f"형식 오류(THEME_ID:TICKER 아님) — 무시함: {item}")
            continue
        theme_id, ticker = item.split(":", 1)
        exclude.add((theme_id.strip(), ticker.strip().upper()))

    approved, excluded = approve_theme_members(conn, run_id, exclude)
    conn.close()

    if approved == 0 and excluded == 0:
        print(f"run_id={run_id}에 해당하는 theme_members가 없습니다 — run_id 오타 확인 필요.")
        sys.exit(1)

    print(f"run_id={run_id}: 승인 {approved}건 / 제외 {excluded}건")
    if excluded < len(exclude):
        print(f"주의: --exclude로 지정한 {len(exclude)}건 중 {excluded}건만 이 run에서 매칭됨 — 나머지는 오타 확인 필요")


if __name__ == "__main__":
    main()
