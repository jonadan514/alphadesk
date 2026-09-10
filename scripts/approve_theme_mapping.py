"""테마 매핑 결과 승인 (SPEC §7).

export_theme_mapping_review.py로 뽑은 CSV를 사람이 검토한 뒤, 문제없으면
approved=1로 확정한다. 제외하기로 한 것만 --exclude로 넘기면 나머지는 전부
승인된다. 제외된 행은 삭제되지 않고 approved=0으로 남는다(이력 보존).

Usage:
  python scripts/approve_theme_mapping.py                                    # 최신 run 전체 승인
  python scripts/approve_theme_mapping.py --run-id 20260901012050-53eebe
  python scripts/approve_theme_mapping.py --exclude nuclear_smr:034730 shipbuilding:BA
  python scripts/approve_theme_mapping.py --only-market KR   # KR 행만 승인, 나머지는 approved=0

--only-market이 필요한 이유: 매핑은 US·KR을 한 run에서 같이 만들지만, 변경
사유가 한쪽 시장에만 있는 경우가 있다(예: KR 유니버스 확장). 이때 전체를
승인하면 사유가 없는 쪽까지 LLM 재실행 편차로 바뀐다 — 2026-09-09 코스피200
확장 때 US 소속이 191 -> 177로 줄고 nuclear_smr US가 0이 되는 것을 확인했다.
소속 조회는 (theme_id, market)별로 승인된 최신 run을 고르므로, 한쪽 시장만
승인하면 다른 시장은 기존 매핑에 그대로 남는다.
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
    parser.add_argument("--only-market", default=None, choices=["US", "KR"],
                         help="이 시장의 행만 승인한다. 나머지 시장 행은 approved=0으로 남아 "
                              "해당 시장은 기존 승인 매핑을 계속 쓴다.")
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

    if args.only_market:
        # DB 값을 그대로 넣는다 — approve_theme_members가 조회한 행과 문자열
        # 비교를 하므로 위쪽 --exclude 파싱처럼 upper()를 씌우면 안 된다.
        others = conn.execute(
            "SELECT theme_id, ticker FROM theme_members WHERE run_id = ? AND market != ?",
            (run_id, args.only_market),
        ).fetchall()
        for theme_id, ticker in others:
            exclude.add((theme_id, ticker))
        print(f"--only-market {args.only_market}: 다른 시장 {len(others)}건을 제외 목록에 추가")

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
