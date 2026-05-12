import os
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
OUTPUT_DIR = Path(__file__).parents[4] / "data"

SERIES = {
    "DFF":            "fed_funds_rate",
    "T10Y2Y":         "yield_spread_10y2y",
    "T10YIE":         "breakeven_10y",
    "T5YIE":          "breakeven_5y",
    "BAMLH0A0HYM2":   "hy_spread",
    "BAMLC0A0CM":     "ig_spread",
    "UNRATE":         "unemployment",
    "ICSA":           "initial_claims",
    "CPIAUCSL":       "cpi",
    "CPILFESL":       "core_cpi",
    "PCEPI":          "pce",
    "PCEPILFE":       "core_pce",
    "INDPRO":         "industrial_production",
    "RETAILSMNSA":    "retail_sales",
    "HOUST":          "housing_starts",
    "UMCSENT":        "consumer_sentiment",
    "DTWEXBGS":       "dollar_index",
    "DCOILWTICO":     "wti_oil",
    "GOLDAMGBD228NLBM": "gold",
    "VIXCLS":         "vix",
    "M2SL":           "m2",
    "BOGMBASE":       "monetary_base",
    "TOTCI":          "commercial_loans",
    "DRSFRMACBS":     "mortgage_rate",
    "CSUSHPISA":      "case_shiller_hpi",
}

Z_WINDOW   = 60
MOM_WINDOW = 20


def _fetch_series(series_id: str, api_key: str, observation_start: str) -> pd.Series:
    params = {
        "series_id":         series_id,
        "api_key":           api_key,
        "file_type":         "json",
        "observation_start": observation_start,
        "sort_order":        "asc",
    }
    try:
        resp = requests.get(FRED_BASE, params=params, timeout=15)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        s = pd.Series(
            {o["date"]: float(o["value"]) for o in obs if o["value"] != "."},
            name=series_id,
        )
        return s
    except Exception as exc:
        print(f"[build_macro_features] FRED {series_id} error: {exc}")
        return pd.Series(name=series_id, dtype=float)


def build_macro_features() -> pd.DataFrame:
    api_key = os.getenv("FRED_API_KEY", "")
    if not api_key:
        raise EnvironmentError("FRED_API_KEY not set")

    start = (datetime.today() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")

    raw: dict[str, pd.Series] = {}
    for series_id, label in SERIES.items():
        s = _fetch_series(series_id, api_key, start)
        if not s.empty:
            raw[label] = s

    if not raw:
        raise RuntimeError("No FRED data fetched")

    base = pd.DataFrame(raw)
    base.index = pd.to_datetime(base.index)
    base = base.sort_index().ffill()

    feats = pd.DataFrame(index=base.index)

    for col in base.columns:
        s = base[col]
        # Z-score (60d rolling)
        roll_mean = s.rolling(Z_WINDOW).mean()
        roll_std  = s.rolling(Z_WINDOW).std().replace(0, np.nan)
        feats[f"{col}_zscore"]   = (s - roll_mean) / roll_std

        # Momentum (20d % change)
        feats[f"{col}_mom20"]    = s.pct_change(MOM_WINDOW)

        # Level (raw, forward-filled)
        feats[f"{col}_level"]    = s

    # Derived spreads
    if "hy_spread" in base.columns and "ig_spread" in base.columns:
        feats["hy_ig_spread"]    = base["hy_spread"] - base["ig_spread"]

    if "breakeven_10y" in base.columns and "fed_funds_rate" in base.columns:
        feats["real_rate_proxy"] = base["breakeven_10y"] - base["fed_funds_rate"]

    feats = feats.dropna(how="all")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.today().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"macro_features_{date_str}.parquet"
    feats.to_parquet(path)
    print(f"Saved macro features {feats.shape} → {path}")
    return feats


if __name__ == "__main__":
    build_macro_features()
