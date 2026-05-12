import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from src.collectors.fetch_sp500_list import fetch_sp500_list
from src.collectors.us_price_fetcher import USPriceFetcher

OUTPUT_PATH = Path(__file__).parents[2] / "data" / "us_daily_prices.csv"
MAX_WORKERS = 5


def _fetch_one(fetcher: USPriceFetcher, symbol: str, period: str) -> tuple[str, pd.DataFrame]:
    return symbol, fetcher.fetch_ohlcv(symbol, period=period)


def fetch_sp500_prices(period: str = "1y") -> pd.DataFrame:
    sp500 = fetch_sp500_list()
    symbols = sp500["Symbol"].tolist()

    fetcher = USPriceFetcher()
    frames: list[pd.DataFrame] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_one, fetcher, sym, period): sym
            for sym in symbols
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Fetching OHLCV"):
            sym = futures[future]
            try:
                _, df = future.result()
                if df.empty:
                    continue
                df = df.copy()
                df["Symbol"] = sym
                frames.append(df)
            except Exception as exc:
                print(f"[fetch_sp500_prices] {sym} skipped: {exc}")

    if not frames:
        print("No data fetched.")
        return pd.DataFrame()

    combined = pd.concat(frames)
    combined.index.name = "Date"
    combined = combined.reset_index()
    combined = combined[["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"]]
    combined = combined.sort_values(["Symbol", "Date"]).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(combined):,} rows ({combined['Symbol'].nunique()} tickers) → {OUTPUT_PATH}")
    return combined


if __name__ == "__main__":
    fetch_sp500_prices()
