import os
import requests
import yfinance as yf
from curl_cffi import requests as curl_requests
from dotenv import load_dotenv

load_dotenv()

FINNHUB_BASE = "https://finnhub.io/api/v1"

YFINANCE_FIELDS = {
    "trailingPE": "pe_trailing",
    "forwardPE": "pe_forward",
    "priceToBook": "pb",
    "returnOnEquity": "roe",
    "revenueGrowth": "revenue_growth",
    "earningsGrowth": "earnings_growth",
    "recommendationMean": "analyst_rating",
    "numberOfAnalystOpinions": "analyst_count",
    "targetMeanPrice": "target_price",
    "currentPrice": "current_price",
    "marketCap": "market_cap",
    "sector": "sector",
    "industry": "industry",
    "shortName": "name",
}


class USStockDataFetcher:
    def __init__(self):
        self._finnhub_key = os.getenv("FINNHUB_API_KEY", "")
        self._session = curl_requests.Session(impersonate="chrome")

    # ------------------------------------------------------------------
    # yfinance
    # ------------------------------------------------------------------
    def _fetch_yfinance(self, symbol: str) -> dict:
        try:
            info = yf.Ticker(symbol, session=self._session).info
            if not info or info.get("trailingPE") is None and info.get("currentPrice") is None:
                return {}
            return {
                dest: info[src]
                for src, dest in YFINANCE_FIELDS.items()
                if info.get(src) is not None
            }
        except Exception as exc:
            print(f"[DataFetcher] yfinance {symbol} error: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Finnhub fallback
    # ------------------------------------------------------------------
    def _fetch_finnhub(self, symbol: str) -> dict:
        if not self._finnhub_key:
            return {}
        result: dict = {}
        headers = {"X-Finnhub-Token": self._finnhub_key}
        try:
            # Basic financials
            r = requests.get(
                f"{FINNHUB_BASE}/stock/metric",
                params={"symbol": symbol, "metric": "all"},
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
            metric = r.json().get("metric", {})
            mapping = {
                "peBasicExclExtraTTM": "pe_trailing",
                "pbAnnual": "pb",
                "roeRfy": "roe",
                "revenueGrowthTTMYoy": "revenue_growth",
            }
            for src, dest in mapping.items():
                if metric.get(src) is not None:
                    result[dest] = metric[src]

            # Analyst targets
            r2 = requests.get(
                f"{FINNHUB_BASE}/stock/price-target",
                params={"symbol": symbol},
                headers=headers,
                timeout=10,
            )
            r2.raise_for_status()
            pt = r2.json()
            if pt.get("targetMean") is not None:
                result["target_price"] = pt["targetMean"]
            if pt.get("lastUpdated"):
                result["target_updated"] = pt["lastUpdated"]
        except Exception as exc:
            print(f"[DataFetcher] Finnhub {symbol} error: {exc}")
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, symbol: str) -> dict:
        data = self._fetch_yfinance(symbol)
        if not data:
            data = self._fetch_finnhub(symbol)
        elif self._finnhub_key:
            # fill missing fields from Finnhub
            fallback = self._fetch_finnhub(symbol)
            for k, v in fallback.items():
                if k not in data:
                    data[k] = v
        data["symbol"] = symbol
        return data
