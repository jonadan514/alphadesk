"""Phase B 착수 판단용 - theme_members에 이미 매핑된 한국(KR) 기업이 몇 개나
있는지 테마별로 확인하는 읽기 전용 임시 스크립트. 확인 후 삭제."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

conn = get_db()

# 테마별 최신 승인 run_id + approved=1 기준 (SPEC §5와 동일한 관례)
rows = conn.execute("""
    WITH latest_runs AS (
        SELECT theme_id, MAX(run_id) AS run_id
        FROM theme_members
        WHERE market = 'KR' AND approved = 1
        GROUP BY theme_id
    )
    SELECT tm.theme_id, COUNT(*) AS n
    FROM theme_members tm
    JOIN latest_runs lr ON lr.theme_id = tm.theme_id AND lr.run_id = tm.run_id
    WHERE tm.market = 'KR' AND tm.approved = 1
    GROUP BY tm.theme_id
    ORDER BY n DESC
""").fetchall()

print("=== 테마별 KR 승인 소속 기업 수 (approved=1, 최신 run) ===")
total = 0
for theme_id, n in rows:
    n = int(n)
    total += n
    print(f"  {theme_id}: {n}")
print(f"합계: {total}개 (테마 {len(rows)}개에 분포)")

# approved 여부 상관없이 원본(매핑 시도 자체) 개수도 확인 - 승인 안 된 것도 있는지
raw = conn.execute("""
    SELECT theme_id, approved, COUNT(*) FROM theme_members
    WHERE market = 'KR'
    GROUP BY theme_id, approved
    ORDER BY theme_id
""").fetchall()
print()
print("=== 원본(승인여부 무관) KR 매핑 현황 ===")
for theme_id, approved, n in raw:
    print(f"  {theme_id}: approved={approved} n={int(n)}")

# 한국 전용 테마 3개 특정 확인
print()
print("=== 한국 전용 테마(k_beauty/k_food/k_content) ===")
for tid in ["k_beauty", "k_food", "k_content"]:
    r = conn.execute(
        "SELECT ticker, linkage, confidence, approved FROM theme_members WHERE theme_id = ? AND market = 'KR'",
        (tid,),
    ).fetchall()
    print(f"  {tid}: {len(r)}건")
    for ticker, linkage, confidence, approved in r[:10]:
        print(f"    {ticker} linkage={linkage} confidence={confidence} approved={approved}")

conn.close()
