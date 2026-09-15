"""승인된 테마 소속을 승인 해제한다 (행은 남기고 approved만 0).

용도: 승인 후 검토에서 틀린 편입으로 확정된 행을 화면에서 내린다. 행을 지우지 않으므로
이력은 보존된다(CLAUDE.md 원칙 5). 해제 사유는 검토 파일(data/eval/*.json)에 남긴다.

두 가지 방식:
  --items THEME:TICKER ...   지정한 run 안의 특정 행만 해제
  --empty-theme THEME        그 테마·시장의 승인분을 모든 run에서 해제 - "검토 결과 해당
                             기업 없음"을 표현하는 유일한 방법이다. 화면은 테마별로 승인된
                             최신 run을 고르므로, 최신 run에 행이 없으면 더 오래된 승인분이
                             줄줄이 드러난다(2026-09-15 rare_earth: 엘앤에프를 해제하자 더
                             예전 run의 영풍이 표시됐다).

Turso HTTP 클라이언트는 UPDATE 영향 행 수를 돌려주지 않으므로, 변경 전후를 재조회해
실제 반영 여부를 확인한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db  # noqa: E402


def _count(conn, sql: str, args: tuple) -> int:
    return int(conn.execute(sql, args).fetchone()[0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None, help="--items 대상 run")
    ap.add_argument("--items", nargs="*", default=[], metavar="THEME:TICKER")
    ap.add_argument("--empty-theme", nargs="*", default=[], metavar="THEME")
    ap.add_argument("--market", default="KR")
    args = ap.parse_args()
    items = [x for x in (args.items or []) if x]
    empties = [x for x in (args.empty_theme or []) if x]
    if items and not args.run_id:
        print("--items 는 --run-id 가 필요하다")
        return 1

    conn = get_db()
    problems = 0

    for it in items:
        if ":" not in it:
            print(f"형식 오류 무시: {it}")
            problems += 1
            continue
        tid, code = it.split(":", 1)
        where = "theme_id = ? AND ticker = ? AND market = ? AND run_id = ?"
        a = (tid, code, args.market, args.run_id)
        before = _count(conn, f"SELECT COUNT(*) FROM theme_members WHERE {where} AND approved = 1", a)
        exists = _count(conn, f"SELECT COUNT(*) FROM theme_members WHERE {where}", a)
        conn.execute(f"UPDATE theme_members SET approved = 0 WHERE {where}", a)
        conn.commit()
        after = _count(conn, f"SELECT COUNT(*) FROM theme_members WHERE {where} AND approved = 1", a)
        status = "OK" if exists and after == 0 else ("행 없음 - 오타 확인" if not exists else "해제 실패")
        if status != "OK":
            problems += 1
        print(f"  [{status}] {tid} {code} run={args.run_id} 승인 {before} -> {after}")

    for tid in empties:
        a = (tid, args.market)
        rows = conn.execute(
            "SELECT run_id, ticker FROM theme_members WHERE theme_id = ? AND market = ? AND approved = 1 ORDER BY run_id",
            a,
        ).fetchall()
        conn.execute("UPDATE theme_members SET approved = 0 WHERE theme_id = ? AND market = ? AND approved = 1", a)
        conn.commit()
        after = _count(conn, "SELECT COUNT(*) FROM theme_members WHERE theme_id = ? AND market = ? AND approved = 1", a)
        status = "OK" if after == 0 else "해제 실패"
        if status != "OK":
            problems += 1
        print(f"  [{status}] 테마 비우기 {tid} {args.market}: 승인 {len(rows)} -> {after} "
              f"(해제된 행: {[(r[0], r[1]) for r in rows]})")

    conn.close()
    print(f"완료 - 문제 {problems}건")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
