"""§4 검증 — 트랩 필터를 라이브 데이터로 돌린 결과와 캐시로 돌린 결과를 비교한다.

SPEC 완료 조건(SPEC_fundamentals_cache.md §9): "캐시 적용 전후 통과 종목 목록이
동일해야 한다." 이 스크립트가 그 비교를 1회성으로 수행한다.

주간 파이프라인(run_watchlist_screen.py)은 이 스크립트가 아직 바꾸지 않는다 —
검증 전용. 백필로 이미 성공(status='ok')한 종목만 비교 대상으로 삼는다
(아직 캐시 안 된 종목을 넣으면 "캐시가 비어서 다르다"는 당연한 잡음만 늘어남).

라이브 재조회가 들어가므로 백필과 동일하게 offset/limit로 나눠 돌린다.

Usage:
  python scripts/compare_trap_filter_cache.py --offset 0 --limit 50 --market ALL
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.fundamentals_cache import ensure_schema, get_cached_financials
from collectors.watchlist_collector import get_us_universe, get_kr_universe, fetch_financials
from analyzers.trap_filter import apply_trap_filters

SLEEP_BETWEEN_TICKERS = 1.0


def _yf_symbol_map(market: str) -> dict[str, str]:
    items: list[dict] = []
    if market in ("US", "ALL"):
        items += get_us_universe()
    if market in ("KR", "ALL"):
        items += get_kr_universe()
    return {it["symbol"]: it["yf_symbol"] for it in items}


def _compare_one(live_result: dict, cache_result: dict) -> list[str]:
    """다른 필드들 이름 목록. 비어있으면 완전 일치."""
    diffs = []
    for key in ("status", "piotroski", "debt_ratio", "interest_coverage", "roe", "regime_fit"):
        if live_result.get(key) != cache_result.get(key):
            diffs.append(key)
    return diffs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--market", choices=["US", "KR", "ALL"], default="ALL")
    args = parser.parse_args()

    conn = get_db()
    ensure_schema(conn)

    symbol_to_yf = _yf_symbol_map(args.market)

    if args.market == "ALL":
        status_rows = conn.execute(
            "SELECT ticker, market FROM fetch_status WHERE status = 'ok' ORDER BY ticker"
        ).fetchall()
    else:
        status_rows = conn.execute(
            "SELECT ticker, market FROM fetch_status WHERE status = 'ok' AND market = ? ORDER BY ticker",
            (args.market,),
        ).fetchall()

    chunk = status_rows[args.offset: args.offset + args.limit]
    print(f"[compare] 백필 성공 종목 {len(status_rows)}개(market={args.market}) 중 "
          f"offset={args.offset} limit={args.limit} → {len(chunk)}개 비교")

    if not chunk:
        print("[compare] 비교할 종목이 없습니다.")
        return

    matched, mismatched, skipped = 0, [], 0

    for i, (ticker, market) in enumerate(chunk, 1):
        yf_symbol = symbol_to_yf.get(ticker)
        if not yf_symbol:
            # 백필 이후 유니버스에서 빠진 종목(지수 편입 변경 등) — 비교 불가, 건너뜀
            skipped += 1
            print(f"  [{i}/{len(chunk)}] {ticker}: 건너뜀 (현재 유니버스에 없음)")
            continue

        cache_data = get_cached_financials(conn, ticker)
        if cache_data is None:
            skipped += 1
            print(f"  [{i}/{len(chunk)}] {ticker}: 건너뜀 (캐시 비어있음 — 백필 상태와 불일치, 확인 필요)")
            continue

        live_data = fetch_financials(yf_symbol)
        time.sleep(SLEEP_BETWEEN_TICKERS)
        if live_data is None:
            skipped += 1
            print(f"  [{i}/{len(chunk)}] {ticker}: 건너뜀 (지금 라이브 조회 실패 — 야후 일시 오류일 수 있음)")
            continue

        cache_item = {"symbol": ticker, "sector": (cache_data.get("info") or {}).get("sector", ""),
                      "financials_data": cache_data}
        live_item = {"symbol": ticker, "sector": (live_data.get("info") or {}).get("sector", ""),
                     "financials_data": live_data}

        cache_result = apply_trap_filters(cache_item)
        live_result = apply_trap_filters(live_item)

        diffs = _compare_one(live_result, cache_result)
        if diffs:
            mismatched.append((ticker, diffs, live_result, cache_result))
            print(f"  [{i}/{len(chunk)}] {ticker}: 불일치 필드={diffs} "
                  f"(live={live_result.get('status')}/{live_result.get('piotroski')}, "
                  f"cache={cache_result.get('status')}/{cache_result.get('piotroski')})")
        else:
            matched += 1
            print(f"  [{i}/{len(chunk)}] {ticker}: 일치 (status={live_result.get('status')})")

    conn.close()

    print("=" * 60)
    print(f"[compare] 완료 — 비교 {len(chunk) - skipped} / 일치 {matched} / "
          f"불일치 {len(mismatched)} / 건너뜀 {skipped}")
    if mismatched:
        print("\n불일치 상세:")
        for ticker, diffs, live_result, cache_result in mismatched:
            print(f"  {ticker}: {diffs}")
            print(f"    live : status={live_result.get('status')} red_flags={live_result.get('red_flags')}")
            print(f"    cache: status={cache_result.get('status')} red_flags={cache_result.get('red_flags')}")
        print(
            "\n불일치가 나왔다고 전부 버그는 아닙니다 — 백필 이후 새 분기 실적이 발표돼"
            " 라이브 쪽에만 최신 회계기간이 잡히는 경우 정상적으로 값이 달라질 수 있습니다."
            " status가 pass/fail 사이에서 뒤집힌 경우만 자세히 볼 것."
        )


if __name__ == "__main__":
    main()
