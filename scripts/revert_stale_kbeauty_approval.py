"""run_id=20260905135239-8faa38의 k_beauty 5건을 approved=0으로 되돌린다.

이 run은 k_beauty+k_food를 한 번에 재매핑한 것인데, k_food(삼성SDS 제외 7건)만
승인할 생각이었다가 실수로 k_beauty(근거 오류 2건 포함, 미교정) 5건도 함께
승인해버렸다. 이후 별도로 k_beauty만 다시 매핑한 run(20260905135756-ce247e,
근거 교정 완료)이 있어 MAX(run_id) 기준으로는 실제 화면에 영향이 없지만,
틀린 근거가 approved=1로 DB에 남아있는 건 위생상 좋지 않아 되돌린다.
삭제는 안 하고 approved=0으로만 되돌려 이력은 남긴다.

Usage:
  python scripts/revert_stale_kbeauty_approval.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

STALE_RUN_ID = "20260905135239-8faa38"


def _log(msg: str) -> None:
    print(f"[revert] {msg}")


def main() -> None:
    conn = get_db()
    rows = conn.execute(
        "SELECT ticker, approved FROM theme_members WHERE theme_id = 'k_beauty' AND run_id = ?",
        (STALE_RUN_ID,),
    ).fetchall()
    _log(f"대상 run_id={STALE_RUN_ID}의 k_beauty 행: {len(rows)}건")
    for ticker, approved in rows:
        _log(f"  {ticker}: approved={approved}")

    conn.execute(
        "UPDATE theme_members SET approved = 0 WHERE theme_id = 'k_beauty' AND run_id = ?",
        (STALE_RUN_ID,),
    )
    conn.commit()
    conn.close()
    _log("완료 - approved=0으로 되돌림 (삭제 아님)")


if __name__ == "__main__":
    main()
