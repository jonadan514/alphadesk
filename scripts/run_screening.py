"""
S&P 500 스크리닝 단독 실행
Usage: python scripts/run_screening.py [--top N]
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import argparse
import pandas as pd
from tqdm import tqdm

from src.collectors.fetch_sp500_list import fetch_sp500_list
from src.collectors.us_price_fetcher import USPriceFetcher
from src.analyzers.smart_money_screener_v2 import EnhancedSmartMoneyScreener

SP500_CSV  = ROOT / "data" / "sp500_list.csv"
PRICES_CSV = ROOT / "data" / "us_daily_prices.csv"


def load_price_map() -> dict[str, pd.DataFrame]:
    if not PRICES_CSV.exists():
        print("[run_screening] prices CSV 없음, 빈 price_map으로 진행")
        return {}
    df = pd.read_csv(PRICES_CSV)
    df["Date"] = pd.to_datetime(df["Date"])
    price_map: dict[str, pd.DataFrame] = {}
    for sym, grp in tqdm(df.groupby("Symbol"), desc="가격 데이터 로드", leave=False):
        price_map[sym] = grp.set_index("Date").sort_index()
    return price_map


def main() -> None:
    parser = argparse.ArgumentParser(description="S&P 500 스크리닝")
    parser.add_argument("--top", type=int, default=20, help="상위 N개 선별 (기본: 20)")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 55)
    print("  S&P 500 스마트머니 스크리닝")
    print("=" * 55)

    # S&P 500 종목 로드
    if SP500_CSV.exists():
        sp500_df = pd.read_csv(SP500_CSV)
        print(f"[load] sp500_list.csv  →  {len(sp500_df)}종목")
    else:
        print("[load] sp500_list.csv 없음, Wikipedia 재수집 중…")
        from src.collectors.fetch_sp500_list import save_sp500_list
        sp500_df = save_sp500_list()

    symbols  = sp500_df["Symbol"].tolist()
    price_map = load_price_map()

    # 스크리닝
    screener = EnhancedSmartMoneyScreener()

    # wrap symbols with tqdm for progress display
    scored_rows = []
    for sym in tqdm(symbols, desc="종목 평가 중", unit="종목"):
        try:
            row = screener._score_symbol(sym, price_map)
            if row:
                scored_rows.append(row)
        except Exception as exc:
            tqdm.write(f"  [skip] {sym}: {exc}")

    if not scored_rows:
        print("스크리닝 결과 없음.")
        return

    picks_df = (
        pd.DataFrame(scored_rows)
        .sort_values("composite_score", ascending=False)
        .head(args.top)
        .reset_index(drop=True)
    )
    picks_df.index += 1

    # CSV 저장
    from datetime import datetime
    from pathlib import Path
    out_dir = ROOT / "output" / "picks"
    out_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.today().strftime("%Y%m%d")
    out_path = out_dir / f"smart_money_picks_{date_str}.csv"
    picks_df.to_csv(out_path, index=True, index_label="rank")
    print(f"\n저장 완료: {out_path}")

    # 상위 10개 출력
    display_cols = ["symbol", "composite_score", "grade",
                    "technical", "fundamental", "analyst",
                    "relative_strength", "volume", "sector"]
    display_cols = [c for c in display_cols if c in picks_df.columns]
    print(f"\n── 상위 {min(10, len(picks_df))}개 ──────────────────────────")
    print(picks_df[display_cols].head(10).to_string())
    print(f"\n총 소요: {time.time()-t0:.1f}초")


if __name__ == "__main__":
    main()
