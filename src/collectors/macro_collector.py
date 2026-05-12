import os
import requests
import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES = {
    "DFF": "Fed Funds Rate",
    "T10Y2Y": "10Y-2Y Spread",
    "BAMLH0A0HYM2": "HY Spread (OAS)",
}
FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


class MacroDataCollector:
    def __init__(self):
        self._fred_key = os.getenv("FRED_API_KEY", "")
        self._session = curl_requests.Session(impersonate="chrome")

    # ------------------------------------------------------------------
    # FRED
    # ------------------------------------------------------------------
    def _fetch_fred_series(self, series_id: str, limit: int = 30) -> pd.Series:
        if not self._fred_key:
            return pd.Series(dtype=float)
        params = {
            "series_id": series_id,
            "api_key": self._fred_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        try:
            resp = requests.get(FRED_BASE, params=params, timeout=10)
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            s = pd.Series(
                {o["date"]: float(o["value"]) for o in obs if o["value"] != "."}
            )
            return s.sort_index()
        except Exception as exc:
            print(f"[MacroCollector] FRED {series_id} error: {exc}")
            return pd.Series(dtype=float)

    def get_fred_latest(self) -> dict:
        result = {}
        for sid, label in FRED_SERIES.items():
            s = self._fetch_fred_series(sid, limit=5)
            result[sid] = {
                "label": label,
                "value": round(s.iloc[-1], 4) if not s.empty else None,
                "date": s.index[-1] if not s.empty else None,
            }
        return result

    # ------------------------------------------------------------------
    # VIX
    # ------------------------------------------------------------------
    def get_vix(self) -> dict:
        try:
            ticker = yf.Ticker("^VIX", session=self._session)
            df = ticker.history(period="3mo", auto_adjust=True)
            if df is None or df.empty:
                return {}
            close = df["Close"]
            current = round(float(close.iloc[-1]), 2)
            ma20 = round(float(close.tail(20).mean()), 2)
            trend = "상승" if current > ma20 else "하락"
            return {
                "current": current,
                "ma20": ma20,
                "trend": trend,
                "date": str(df.index[-1].date()),
            }
        except Exception as exc:
            print(f"[MacroCollector] VIX error: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Fear & Greed
    # ------------------------------------------------------------------
    def get_fear_greed(self) -> dict:
        try:
            resp = self._session.get(FEAR_GREED_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            fg = data.get("fear_and_greed", {})
            score = fg.get("score")
            rating = fg.get("rating", "")
            return {
                "score": round(float(score), 1) if score is not None else None,
                "rating": rating,
            }
        except Exception as exc:
            print(f"[MacroCollector] Fear&Greed error: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def get_macro_summary(self) -> dict:
        fred = self.get_fred_latest()
        vix = self.get_vix()
        fg = self.get_fear_greed()
        return {
            "collected_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fred": fred,
            "vix": vix,
            "fear_greed": fg,
        }
