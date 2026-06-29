"""워치리스트 종목 유니버스 수집기.

US: S&P 500 + S&P 400 (시가총액 $2B+)
KR: KOSPI + KOSDAQ (시가총액 2000억+, 한국상장중국기업 제외)
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SP500_CSV = REPO_ROOT / "data" / "sp500_list.csv"

US_MIN_CAP = 2_000_000_000        # $2B
KR_MIN_CAP = 200_000_000_000      # 2000억원


def get_us_universe() -> list[dict]:
    """S&P 500 기반 미국 유니버스."""
    tickers: list[str] = []

    if SP500_CSV.exists():
        df = pd.read_csv(SP500_CSV)
        col = next((c for c in df.columns if "symbol" in c.lower() or "ticker" in c.lower()), df.columns[0])
        tickers = df[col].str.replace(".", "-", regex=False).dropna().tolist()
    else:
        try:
            df = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
            tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        except Exception as e:
            logger.error("S&P 500 목록 수집 실패: %s", e)
            return []

    return [{"market": "US", "symbol": t, "yf_symbol": t} for t in tickers]


def get_kr_universe() -> list[dict]:
    """KOSPI + KOSDAQ 유니버스 (pykrx 사용)."""
    try:
        from pykrx import stock as pykrx_stock
        from datetime import date

        today = date.today().strftime("%Y%m%d")
        result = []

        for exchange in ["KOSPI", "KOSDAQ"]:
            tickers = pykrx_stock.get_market_ticker_list(today, market=exchange)
            for ticker in tickers:
                try:
                    name = pykrx_stock.get_market_ticker_name(ticker)
                    cap_df = pykrx_stock.get_market_cap(today, today, ticker)
                    if cap_df.empty:
                        continue
                    market_cap = int(cap_df["시가총액"].iloc[-1])
                    if market_cap < KR_MIN_CAP:
                        continue
                    suffix = ".KS" if exchange == "KOSPI" else ".KQ"
                    result.append({
                        "market": "KR",
                        "symbol": ticker,
                        "yf_symbol": ticker + suffix,
                        "name": name,
                        "market_cap": market_cap,
                        "exchange": exchange,
                    })
                except Exception:
                    continue

        logger.info("KR 유니버스: %d 종목 (2000억+ 필터 후)", len(result))
        return result

    except ImportError:
        logger.warning("pykrx 미설치 — KR 유니버스 수집 불가. pip install pykrx")
        return []


def fetch_financials(yf_symbol: str, retries: int = 2) -> dict | None:
    """yfinance로 재무 데이터 수집. 실패 시 None 반환."""
    for attempt in range(retries + 1):
        try:
            t = yf.Ticker(yf_symbol)
            info = t.info or {}

            # 기본 정보 없으면 스킵
            if not info.get("symbol") and not info.get("shortName"):
                return None

            fin = t.financials          # income statement (annual)
            bs  = t.balance_sheet       # balance sheet (annual)
            cf  = t.cashflow            # cash flow (annual)

            return {
                "info": info,
                "financials": fin,
                "balance_sheet": bs,
                "cashflow": cf,
            }
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                logger.debug("재무 데이터 수집 실패 %s: %s", yf_symbol, e)
                return None


def is_chinese_kr_listing(info: dict) -> bool:
    """한국 상장 중국기업 여부 판별."""
    country = (info.get("country") or "").lower()
    return country in ("china", "cn", "hong kong", "hk")


def collect_universe(markets: list[str] = ("US", "KR")) -> list[dict]:
    """전체 유니버스 수집 + 재무 데이터 포함."""
    items = []
    if "US" in markets:
        items += get_us_universe()
    if "KR" in markets:
        items += get_kr_universe()

    logger.info("총 유니버스: %d 종목 (재무 수집 시작)", len(items))

    result = []
    for i, item in enumerate(items):
        if i % 50 == 0:
            logger.info("진행: %d / %d", i, len(items))

        data = fetch_financials(item["yf_symbol"])
        if data is None:
            continue

        # 한국 상장 중국기업 제외
        if item["market"] == "KR" and is_chinese_kr_listing(data["info"]):
            logger.debug("한국상장중국기업 제외: %s", item["symbol"])
            continue

        # 시가총액 필터 (US는 yfinance에서 다시 확인)
        if item["market"] == "US":
            cap = data["info"].get("marketCap") or 0
            if cap < US_MIN_CAP:
                continue
            item["market_cap"] = cap
        elif "market_cap" not in item:
            item["market_cap"] = data["info"].get("marketCap") or 0

        item["name"] = item.get("name") or data["info"].get("shortName") or item["symbol"]
        item["sector"] = data["info"].get("sector") or data["info"].get("industry") or "Unknown"
        item["financials_data"] = data

        result.append(item)
        time.sleep(0.3)  # rate limiting

    logger.info("재무 데이터 수집 완료: %d 종목", len(result))
    return result
