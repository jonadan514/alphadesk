"""초기 백필 — 유니버스 재무제표를 fundamentals_cache/fetch_status에 채운다.

SPEC: docs/radar/SPEC_fundamentals_cache.md §5

사람이 여러 번에 나눠 수동 실행한다 (offset/limit로 구간 지정). 종목 하나
처리할 때마다 즉시 커밋하므로, 중간에 실패해도 앞서 받은 것은 남는다.

Usage:
  python scripts/backfill_fundamentals.py --offset 0  --limit 50 --market ALL
  python scripts/backfill_fundamentals.py --offset 50 --limit 50 --market US
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.fundamentals_cache import ensure_schema, upsert_statement_rows, upsert_fetch_status
from collectors.watchlist_collector import get_us_universe, get_kr_universe, fetch_financials

SLEEP_BETWEEN_TICKERS = 1.0  # 초 — 백필 자체가 야후를 과호출하지 않도록


def _sorted_universe(market: str) -> list[dict]:
    items: list[dict] = []
    if market in ("US", "ALL"):
        items += get_us_universe()
    if market in ("KR", "ALL"):
        items += get_kr_universe()
    items.sort(key=lambda x: x["yf_symbol"])  # 티커 사전순 고정 정렬 — offset/limit가 매번 같은 구간을 가리키게
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--market", choices=["US", "KR", "ALL"], default="ALL")
    args = parser.parse_args()

    universe = _sorted_universe(args.market)
    chunk = universe[args.offset: args.offset + args.limit]
    print(f"[backfill] 유니버스 {len(universe)}종목 (market={args.market}) 중 "
          f"offset={args.offset} limit={args.limit} → {len(chunk)}종목 처리")

    if not chunk:
        print("[backfill] 처리할 종목이 없습니다 (offset이 유니버스 크기를 넘었을 수 있음)")
        return

    conn = get_db()
    ensure_schema(conn)

    counts = {"처리": 0, "성공": 0, "rate_limited": 0, "no_data": 0}

    for i, item in enumerate(chunk, 1):
        ticker, yf_symbol, market = item["symbol"], item["yf_symbol"], item["market"]
        now = datetime.utcnow().isoformat()  # run_watchlist_screen.py와 동일 포맷(naive UTC)으로 통일
        counts["처리"] += 1

        try:
            data = fetch_financials(yf_symbol)

            if data is None:
                upsert_fetch_status(conn, ticker, market, now, status="no_data")
                counts["no_data"] += 1
                print(f"  [{i}/{len(chunk)}] {ticker}: 실패 (no_data)")
            else:
                n = 0
                n += upsert_statement_rows(conn, ticker, market, "income", data["financials"], now)
                n += upsert_statement_rows(conn, ticker, market, "balance", data["balance_sheet"], now)
                n += upsert_statement_rows(conn, ticker, market, "cashflow", data["cashflow"], now)
                upsert_fetch_status(conn, ticker, market, now, status="ok", info=data["info"], success_at=now)
                counts["성공"] += 1
                print(f"  [{i}/{len(chunk)}] {ticker}: 성공 (회계기간 {n}건 기록)")
            conn.commit()
        except Exception as e:
            # fetch_financials() 내부 실패는 이미 잡히지만, 저장 경로(JSON 직렬화 등)에서
            # 예기치 못한 예외가 나도 이 종목만 건너뛰고 나머지 배치는 계속 진행한다 —
            # 이미 커밋된 이전 종목들은 이 예외와 무관하게 보존된다.
            counts["no_data"] += 1
            print(f"  [{i}/{len(chunk)}] {ticker}: 실패 (예외: {type(e).__name__}: {e})")

        time.sleep(SLEEP_BETWEEN_TICKERS)

    conn.close()

    print("=" * 60)
    print(f"[backfill] 완료 — 처리 {counts['처리']} / 성공 {counts['성공']} / "
          f"rate_limited {counts['rate_limited']} / no_data {counts['no_data']}")
    print("(rate_limited은 이번 단계에서 구분하지 않음 — 실패는 전부 no_data로 기록. "
          "지수 백오프 재시도는 §6에서 추가 예정)")


if __name__ == "__main__":
    main()
