import time
import yfinance as yf
import pandas as pd
from curl_cffi import requests as curl_requests


class USPriceFetcher:
    def __init__(self):
        self._session = curl_requests.Session(impersonate="chrome")

    def _make_ticker(self, symbol: str) -> yf.Ticker:
        return yf.Ticker(symbol, session=self._session)

    def fetch_ohlcv(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        last_exc = None
        for attempt in range(3):
            try:
                df = self._make_ticker(symbol).history(period=period, auto_adjust=True)
                if df is None or df.empty:
                    return pd.DataFrame()
                df.index = pd.to_datetime(df.index).tz_localize(None)
                return df[["Open", "High", "Low", "Close", "Volume"]]
            except Exception as exc:
                last_exc = exc
                time.sleep(2 ** attempt)
        print(f"[USPriceFetcher] {symbol} failed after 3 attempts: {last_exc}")
        return pd.DataFrame()

    def fetch_batch(
        self, symbols: list[str], period: str = "1y"
    ) -> dict[str, pd.DataFrame]:
        results: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            results[symbol] = self.fetch_ohlcv(symbol, period=period)
        return results
