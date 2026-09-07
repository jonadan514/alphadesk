"""B-1 뉴스 축 KR 백필 최종 검증 - 확인 후 삭제."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

conn = get_db()

total = conn.execute(
    "SELECT COUNT(DISTINCT theme_id) FROM theme_signals WHERE market = 'KR'"
).fetchone()
print(f"KR 뉴스 신호가 있는 테마 수: {int(total[0])}")

latest_week = conn.execute(
    "SELECT MAX(week_start) FROM theme_signals WHERE market = 'KR'"
).fetchone()[0]
print(f"최신 주: {latest_week}")

rows = conn.execute(
    "SELECT theme_id, news_count, news_baseline, news_arrow FROM theme_signals "
    "WHERE market = 'KR' AND week_start = ? ORDER BY news_count DESC LIMIT 10",
    (latest_week,),
).fetchall()
print("이번 주 뉴스 건수 상위 10개 테마:")
for theme_id, news_count, news_baseline, news_arrow in rows:
    print(f"  {theme_id}: count={news_count} baseline={news_baseline} arrow={news_arrow}")

arrow_dist = conn.execute(
    "SELECT news_arrow, COUNT(*) FROM theme_signals WHERE market = 'KR' AND week_start = ? GROUP BY news_arrow",
    (latest_week,),
).fetchall()
print("이번 주 화살표 분포:")
for arrow, n in arrow_dist:
    print(f"  {arrow}: {int(n)}개")

conn.close()
