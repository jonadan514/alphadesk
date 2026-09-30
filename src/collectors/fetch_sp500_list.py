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


# 예전에는 이 호출이 모듈 수준에 있었다 - import만 해도 위키백과를 긁고 CSV를
# 덮어썼다(run_integrated_analysis.py가 이 모듈을 import한다). 부작용 없이
# import할 수 있어야 테스트도 가능해서 __main__ 가드 안으로 옮겼다.
# 호출부(run_integrated_analysis.py)는 이미 save_sp500_list()를 직접 부르고 있다.
if __name__ == "__main__":
    save_sp500_list()
