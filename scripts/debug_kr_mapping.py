"""k_beauty/k_food 최종 승인 상태 직접 확인 (프론트는 아직 market='US' 고정이라
API로는 못 봄 - DB를 직접 조회). 확인 후 삭제."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

conn = get_db()

for theme_id in ["k_beauty", "k_food"]:
    run_row = conn.execute(
        "SELECT MAX(run_id) FROM theme_members WHERE theme_id = ? AND market = 'KR' AND approved = 1",
        (theme_id,),
    ).fetchone()
    run_id = run_row[0] if run_row else None
    print(f"=== {theme_id} (latest approved run_id={run_id}) ===")
    if not run_id:
        print("  승인된 행 없음")
        continue
    rows = conn.execute(
        "SELECT ticker, linkage, flagged, evidence FROM theme_members "
        "WHERE theme_id = ? AND market = 'KR' AND run_id = ? AND approved = 1",
        (theme_id, run_id),
    ).fetchall()
    print(f"  {len(rows)}건")
    for ticker, linkage, flagged, evidence in rows:
        print(f"    {ticker} linkage={linkage} flagged={flagged} - {evidence}")

conn.close()
