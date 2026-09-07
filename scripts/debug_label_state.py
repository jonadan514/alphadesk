"""라벨이 0개인 원인 진단 - 이번 주 세 축 상태 확인. 확인 후 삭제."""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

conn = get_db()

week = conn.execute(
    "SELECT MAX(week_start) FROM theme_signals WHERE market = 'KR'"
).fetchone()[0]
print(f"KR 최신 주: {week}")
print(f"US 최신 주: {conn.execute(chr(83) + 'ELECT MAX(week_start) FROM theme_signals WHERE market = ' + chr(39) + 'US' + chr(39)).fetchone()[0]}")
print()

for market in ("US", "KR"):
    rows = conn.execute(
        "SELECT theme_id, news_arrow, earn_arrow, price_arrow, news_count, news_baseline "
        "FROM theme_signals WHERE market = ? AND week_start = ? ORDER BY theme_id",
        (market, week),
    ).fetchall()
    print(f"=== {market} ({week}): {len(rows)}행 ===")
    combos = Counter()
    for theme_id, n_a, e_a, p_a, n_cnt, n_base in rows:
        combos[(n_a, e_a, p_a)] += 1
    print("  (뉴스,실적,주가) 조합 분포:")
    for combo, cnt in combos.most_common():
        print(f"    {combo}: {cnt}개")
    print("  샘플 5개:")
    for theme_id, n_a, e_a, p_a, n_cnt, n_base in rows[:5]:
        print(f"    {theme_id}: news={n_a}(count={n_cnt}, baseline={n_base}) earn={e_a} price={p_a}")
    print()

conn.close()
