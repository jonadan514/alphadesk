"""Phase A-4 디버그용 - 특정 티커의 income_quarterly 캐시 상태를 그대로 출력.
문제 진단 끝나면 삭제할 임시 스크립트."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.fundamentals_cache import get_cached_financials_bulk

tickers = sys.argv[1:] or ["TSLA"]
conn = get_db()

rows = conn.execute(
    f"SELECT ticker, period_end, data FROM fundamentals_cache WHERE statement='income_quarterly' "
    f"AND ticker IN ({','.join('?' for _ in tickers)})",
    tickers,
).fetchall()
print(f"raw rows in fundamentals_cache: {len(rows)}")
for ticker, period_end, data in rows:
    print(f"  {ticker} {period_end}: data[:300]={data[:300]}")

bulk = get_cached_financials_bulk(conn, tickers)
for t in tickers:
    d = bulk.get(t)
    if d is None:
        print(f"{t}: bulk 결과 None")
        continue
    qdf = d["financials_quarterly"]
    print(f"{t}: financials_quarterly shape={qdf.shape}, columns={list(qdf.columns)}")
    print(f"  'Total Revenue' in index: {'Total Revenue' in qdf.index}")
    if "Total Revenue" in qdf.index:
        print(f"  values: {qdf.loc['Total Revenue'].tolist()}")
        print(f"  dropna len: {len(qdf.loc['Total Revenue'].dropna())}")

conn.close()
