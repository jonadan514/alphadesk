"""각 (theme_id, market)별로 현재 승인된 최신 run_id를 나열한다.

용도: 검토·승인 라운드를 몇 개 테마에만 돌리고 나면, 손대지 않은 테마가 여전히
오래된(수정 전) run에 머물러 있을 수 있다. 그 run_id의 시각을 보면 어느 라운드
결과인지 역추적할 수 있다 - run_id 앞 14자리가 UTC 타임스탬프(YYYYMMDDHHMMSS)다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db  # noqa: E402


def main() -> int:
    conn = get_db()
    for market in ("KR", "US"):
        print(f"=== {market} ===")
        rows = conn.execute(
            "SELECT theme_id, MAX(run_id) FROM theme_members WHERE market = ? AND approved = 1 "
            "GROUP BY theme_id ORDER BY 2",
            (market,),
        ).fetchall()
        for theme_id, run_id in rows:
            ts = run_id[:14] if run_id and run_id[:14].isdigit() else "?"
            print(f"  {theme_id:24s} {run_id}  (ts={ts})")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
