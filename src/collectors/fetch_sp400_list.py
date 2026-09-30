"""S&P 400 중형주 목록을 위키백과에서 받아 CSV로 저장한다.

fetch_sp500_list.py와 같은 소스·같은 컬럼을 쓴다(Symbol, Security, GICS Sector).
두 파일을 합쳐 미국 유니버스를 만들기 때문에 모양이 같아야 한다
(docs/SPEC_us_universe_sp400.md A-1).

## 왜 중형주를 넣나

미국 테마 32개 중 20개가 소속 기업 5개 미만이었다(중앙값 3개). 원인은 매핑이
아니라 유니버스였다 - S&P 500은 대형주만이라 테마 순수 플레이가 애초에 없다.
희토류(MP)·SMR(BWXT)·태양광 트래커(NXT)·지열(ORA)·산업용 배터리(ENS) 같은
대표 종목이 전부 S&P 400에 있다.

## fetch_sp500_list.py와 다르게 만든 점

그 파일은 맨 아래에서 save_sp500_list()를 **모듈 수준으로 호출**한다 - import만
해도 네트워크를 탄다. 여기서는 __main__ 가드 안에 둔다.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from curl_cffi import requests as curl_requests

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
OUTPUT_PATH = Path(__file__).parents[2] / "data" / "sp400_list.csv"

# 위키백과 S&P 400 문서에는 표가 둘 있다(구성종목, 최근 편입·제외 이력).
# 구성종목 표에는 이 컬럼들이 있고 이력 표에는 없다 - 그걸로 구분한다.
REQUIRED_COLS = ("Symbol", "Security", "GICS Sector")


def fetch_sp400_list() -> pd.DataFrame:
    session = curl_requests.Session(impersonate="chrome")
    resp = session.get(URL, timeout=15)
    resp.raise_for_status()

    tables = pd.read_html(io.StringIO(resp.text))
    for df in tables:
        if all(c in df.columns for c in REQUIRED_COLS):
            out = df[list(REQUIRED_COLS)].copy()
            # 야후 티커 표기: BRK.B -> BRK-B (sp500 쪽과 같은 규칙)
            out["Symbol"] = out["Symbol"].astype(str).str.replace(".", "-", regex=False)
            return out
    raise RuntimeError(
        f"구성종목 표를 찾지 못했다(표 {len(tables)}개). 위키백과 문서 구조가 바뀌었는지 확인할 것.")


def save_sp400_list() -> pd.DataFrame:
    df = fetch_sp400_list()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} tickers → {OUTPUT_PATH}")
    return df


if __name__ == "__main__":
    save_sp400_list()
