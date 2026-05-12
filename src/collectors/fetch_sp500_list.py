import io
import pandas as pd
from pathlib import Path
from curl_cffi import requests as curl_requests

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
OUTPUT_PATH = Path(__file__).parents[2] / "data" / "sp500_list.csv"


def fetch_sp500_list() -> pd.DataFrame:
    session = curl_requests.Session(impersonate="chrome")
    resp = session.get(URL, timeout=15)
    resp.raise_for_status()
    df = pd.read_html(io.StringIO(resp.text))[0]
    df = df[["Symbol", "Security", "GICS Sector"]].copy()
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    return df


def save_sp500_list() -> pd.DataFrame:
    df = fetch_sp500_list()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} tickers → {OUTPUT_PATH}")
    return df


save_sp500_list()
