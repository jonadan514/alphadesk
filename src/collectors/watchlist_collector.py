"""워치리스트 종목 유니버스 수집기.

US: S&P 500 + S&P 400 (시가총액 $2B+)
KR: KOSPI + KOSDAQ (시가총액 2000억+, 한국상장중국기업 제외)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SP500_CSV = REPO_ROOT / "data" / "sp500_list.csv"

US_MIN_CAP = 2_000_000_000        # $2B
KR_MIN_CAP = 200_000_000_000      # 2000억원

# 공공데이터포털 "금융위원회_KRX상장종목정보" — pykrx(data.krx.co.kr 스크래핑)가
# 자동화된 접근을 IP 차단하는 문제(2026-07~08월 4주 연속 실패, pykrx GitHub #170/#151)를
# 우회하기 위한 1차 소스. 무료·자동승인 공식 API라 차단 위험이 훨씬 낮다.
# https://www.data.go.kr/data/15094775/openapi.do 에서 발급받은 서비스키를
# DATA_GO_KR_API_KEY 환경변수(GitHub secret)로 넣어야 동작한다.
KRX_LISTED_INFO_URL = "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo"


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


def _recent_business_day() -> str:
    """주말이면 직전 금요일로 — 크론이 주말에 돌 수 있어 항상 최근 영업일 기준."""
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _kr_all_symbols_public_api(service_key: str) -> list[dict]:
    """공공데이터포털 KRX상장종목정보 API — 전체 KOSPI+KOSDAQ 종목코드 목록.

    시가총액은 이 API에 없다 (기준일자·종목코드·종목명·시장구분만 제공).
    무료·자동승인이라 pykrx처럼 IP 차단당할 위험이 없다.
    """
    import requests

    base_dt = _recent_business_day()
    items: list[dict] = []
    page_no = 1
    num_of_rows = 1000

    while True:
        try:
            resp = requests.get(KRX_LISTED_INFO_URL, params={
                "serviceKey": service_key,
                "numOfRows": num_of_rows,
                "pageNo": page_no,
                "resultType": "json",
                "basDt": base_dt,
            }, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error("공공데이터포털 종목정보 조회 실패 (page %d): %s", page_no, e)
            break

        # 서비스키 미등록이어도 HTTP 200으로 응답하는 경우가 있어 본문을 직접 확인
        if "SERVICE_KEY" in resp.text and "ERROR" in resp.text:
            logger.error("공공데이터포털 서비스키 오류: %s", resp.text[:300])
            break

        try:
            body = resp.json()["response"]
        except Exception as e:
            logger.error("공공데이터포털 응답 파싱 실패: %s / %s", e, resp.text[:300])
            break

        result_code = body.get("header", {}).get("resultCode", "")
        if result_code != "00":
            logger.error("공공데이터포털 API 에러 코드 %s: %s", result_code,
                          body.get("header", {}).get("resultMsg", ""))
            break

        page_items = body.get("body", {}).get("items", {})
        page_items = page_items.get("item", []) if page_items else []
        if isinstance(page_items, dict):  # 결과 1건이면 리스트가 아니라 dict로 옴
            page_items = [page_items]
        if not page_items:
            break

        items.extend(page_items)
        if len(page_items) < num_of_rows:
            break
        page_no += 1

    return items


def _kr_universe_public_api() -> list[dict]:
    """공공데이터포털로 전체 종목코드를 받고, yfinance fast_info로 시가총액을
    빠르게 조회해 2000억+ 만 남긴다 — 전체 재무제표(fetch_financials)는 이후
    collect_universe 단계에서 이 필터를 통과한 종목만 대상으로 돈다.
    """
    service_key = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
    if not service_key:
        logger.warning("DATA_GO_KR_API_KEY 환경변수가 비어있음 (GitHub secret 미등록 또는 워크플로우에 안 넘어옴)")
        return []
    logger.info("DATA_GO_KR_API_KEY 확인됨 (길이 %d자) — 공공데이터포털 조회 시작", len(service_key))

    raw_items = _kr_all_symbols_public_api(service_key)
    if not raw_items:
        logger.warning("공공데이터포털에서 종목을 하나도 못 받음 — 위 에러 로그 확인 필요")
        return []

    candidates = []
    for it in raw_items:
        mkt = it.get("mrktCtg")
        code = it.get("srtnCd")
        if mkt not in ("KOSPI", "KOSDAQ") or not code:
            continue
        candidates.append({
            "symbol": code,
            "name": it.get("itmsNm") or code,
            "exchange": mkt,
            "yf_symbol": f"{code}.KS" if mkt == "KOSPI" else f"{code}.KQ",
        })
    logger.info("공공데이터포털: KOSPI+KOSDAQ %d 종목 코드 확보 — 시가총액 필터링 시작",
                len(candidates))

    result = []
    for i, c in enumerate(candidates):
        if i % 200 == 0:
            logger.info("시가총액 조회 진행: %d / %d", i, len(candidates))
        try:
            cap = yf.Ticker(c["yf_symbol"]).fast_info.get("marketCap")
        except Exception:
            cap = None
        if cap and cap >= KR_MIN_CAP:
            result.append({
                "market": "KR",
                "symbol": c["symbol"],
                "yf_symbol": c["yf_symbol"],
                "name": c["name"],
                "market_cap": int(cap),
                "exchange": c["exchange"],
            })
        time.sleep(0.15)

    logger.info("KR 유니버스(공공데이터포털+yfinance): %d 종목 (2000억+)", len(result))
    return result


def _kr_universe_pykrx() -> list[dict]:
    """KOSPI + KOSDAQ 전체 유니버스 (pykrx) — 보조 폴백.

    data.krx.co.kr을 직접 스크래핑하는 라이브러리라 자동화된(특히 클라우드/CI)
    접근을 IP 차단하는 경우가 흔하다 (pykrx GitHub #170 "IP 차단", #151).
    실제로 2026-07~08월 GitHub Actions에서 4주 연속 0종목으로 실패했다 —
    1차 소스는 위 _kr_universe_public_api(), 이 함수는 그게 막혔을 때만 시도.
    크론이 주말에 돌 수 있으므로 최근 영업일 기준, 시장 전체 일괄 조회.
    """
    try:
        from pykrx import stock as pykrx_stock
    except ImportError:
        logger.warning("pykrx 미설치 — pip install pykrx")
        return []

    try:
        base_date = pykrx_stock.get_nearest_business_day_in_a_week()
    except Exception:
        base_date = _recent_business_day()

    result = []
    for exchange in ["KOSPI", "KOSDAQ"]:
        try:
            cap_df = pykrx_stock.get_market_cap(base_date, market=exchange)
        except Exception as e:
            logger.error("KR %s 시가총액 조회 실패: %s", exchange, type(e).__name__)
            continue
        if cap_df is None or cap_df.empty:
            logger.warning("KR %s 시가총액 데이터 없음 (기준일 %s)", exchange, base_date)
            continue

        big = cap_df[cap_df["시가총액"] >= KR_MIN_CAP]
        suffix = ".KS" if exchange == "KOSPI" else ".KQ"
        for ticker, row in big.iterrows():
            try:
                name = pykrx_stock.get_market_ticker_name(ticker)
            except Exception:
                name = str(ticker)
            result.append({
                "market": "KR",
                "symbol": str(ticker),
                "yf_symbol": str(ticker) + suffix,
                "name": name,
                "market_cap": int(row["시가총액"]),
                "exchange": exchange,
            })

    logger.info("KR 유니버스(pykrx): %d 종목 (기준일 %s, 2000억+)", len(result), base_date)
    return result


def _kr_universe_fallback() -> list[dict]:
    """pykrx 실패 시 폴백: 일간 분석과 동일한 KOSPI 대형주 정적 리스트.

    시가총액은 이후 collect_universe의 yfinance 조회에서 채워진다.
    """
    try:
        from collectors.kr_kospi_list import KOSPI_STOCKS
    except ImportError:
        from src.collectors.kr_kospi_list import KOSPI_STOCKS

    result = [
        {
            "market": "KR",
            "symbol": code,
            "yf_symbol": f"{code}.KS",
            "name": name,
            "exchange": "KOSPI",
        }
        for code, name, _sector in KOSPI_STOCKS
    ]
    logger.info("KR 유니버스(폴백 정적 리스트): %d 종목", len(result))
    return result


def get_kr_universe() -> list[dict]:
    """KR 유니버스. 공공데이터포털(전체, IP 차단 위험 낮음) → pykrx(전체, 종종 차단됨)
    → 정적 대형주 리스트 순으로 시도."""
    universe = _kr_universe_public_api()
    if universe:
        return universe
    logger.warning(
        "공공데이터포털 유니버스 수집 실패(DATA_GO_KR_API_KEY 미설정 또는 API 오류) "
        "— pykrx로 재시도."
    )

    universe = _kr_universe_pykrx()
    if universe:
        return universe
    logger.warning(
        "pykrx 유니버스 수집도 실패 — 정적 리스트로 폴백. "
        "https://www.data.go.kr/data/15094775/openapi.do 에서 서비스키를 발급받아 "
        "DATA_GO_KR_API_KEY로 GitHub secrets에 등록하면 전체 KOSPI+KOSDAQ을 수집합니다."
    )
    return _kr_universe_fallback()


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
        # KR: .KS가 실패했거나 "반쪽 응답"(코스닥 종목을 .KS로 조회하면
        # 재무제표는 오지만 시총·섹터가 비어 옴)이면 코스닥(.KQ)으로 재시도
        needs_kq_retry = (
            item["market"] == "KR"
            and item["yf_symbol"].endswith(".KS")
            and (data is None or not data["info"].get("marketCap"))
        )
        if needs_kq_retry:
            kq_symbol = item["yf_symbol"].replace(".KS", ".KQ")
            kq_data = fetch_financials(kq_symbol)
            if kq_data is not None and kq_data["info"].get("marketCap"):
                data = kq_data
                item["yf_symbol"] = kq_symbol
                item["exchange"] = "KOSDAQ"
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
