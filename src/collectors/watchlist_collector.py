"""워치리스트 종목 유니버스 수집기.

US: S&P 500 + S&P 400 (시가총액 $2B+)
KR: KOSPI + KOSDAQ (시가총액 2000억+, 한국상장중국기업 제외)
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

try:
    from db.data_store import get_db
    from db.fundamentals_cache import (
        ensure_schema, upsert_statement_rows, upsert_fetch_status,
        get_cached_financials, get_cached_financials_bulk, select_refresh_targets,
    )
except ImportError:
    from src.db.data_store import get_db
    from src.db.fundamentals_cache import (
        ensure_schema, upsert_statement_rows, upsert_fetch_status,
        get_cached_financials, get_cached_financials_bulk, select_refresh_targets,
    )

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SP500_CSV = REPO_ROOT / "data" / "sp500_list.csv"

US_MIN_CAP = 2_000_000_000        # $2B
KR_MIN_CAP = 200_000_000_000      # 2000억원

# 공공데이터포털 "금융위원회_KRX상장종목정보" — pykrx(data.krx.co.kr 스크래핑)가
# 자동화된 접근을 IP 차단하는 문제(2026-07~08월 4주 연속 실패, pykrx GitHub #170/#151)를
# 우회해보려 했던 1차 소스. https://www.data.go.kr/data/15094775/openapi.do 에서
# 발급받은 서비스키를 DATA_GO_KR_API_KEY 환경변수(GitHub secret)로 넣으면 동작.
#
# 2026-08-27 확인: 무료·자동승인 공식 API라 지역 차단이 없을 거라 기대했지만,
# GitHub Actions에서 apis.data.go.kr로 TCP 연결 자체가 30초 타임아웃 남
# (ConnectTimeoutError — 해외 IP 자체를 막는 것으로 추정, pykrx와 같은 근본
# 원인). 로컬/한국 리전 환경에서는 될 수도 있어 코드는 그대로 두고 fallback
# 체인의 1차 시도로만 남겨둠 — 실질적으로는 매번 pykrx→정적 리스트로 떨어짐.
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
        result_msg = body.get("header", {}).get("resultMsg", "")
        if result_code != "00":
            logger.error("공공데이터포털 API 에러 코드 %s: %s", result_code, result_msg)
            break

        resp_body = body.get("body", {})
        page_items = resp_body.get("items", {})
        page_items = page_items.get("item", []) if page_items else []
        if isinstance(page_items, dict):  # 결과 1건이면 리스트가 아니라 dict로 옴
            page_items = [page_items]
        if not page_items:
            if page_no == 1:
                logger.warning(
                    "공공데이터포털 정상 응답(resultCode=%s %s)인데 종목 0건 — "
                    "basDt=%s, totalCount=%s, body 원본: %s",
                    result_code, result_msg, base_dt,
                    resp_body.get("totalCount"), resp.text[:500],
                )
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
        from collectors.kr_kospi_list import KOSPI_STOCKS, yf_suffix, exchange_of
    except ImportError:
        from src.collectors.kr_kospi_list import KOSPI_STOCKS, yf_suffix, exchange_of

    # 거래소별로 접미사를 붙인다 - 코스닥 종목에 .KS를 붙이면 yfinance가
    # 에러 대신 조용히 잘못된 응답을 준다(kr_kospi_list.py 주석 참고).
    result = [
        {
            "market": "KR",
            "symbol": code,
            "yf_symbol": f"{code}{yf_suffix(code)}",
            "name": name,
            "exchange": exchange_of(code),
        }
        for code, name, _sector in KOSPI_STOCKS
    ]
    logger.info("KR 유니버스(폴백 정적 리스트): %d 종목", len(result))
    return result


KR_UNIVERSE_FILE = os.getenv("KR_UNIVERSE_FILE") or str(REPO_ROOT / "data" / "kr_universe.json")


def _kr_universe_from_file() -> list[dict]:
    """격리 환경에서 pykrx로 받아둔 전종목 유니버스를 읽는다.

    왜 이 프로세스에서 직접 pykrx를 쓰지 않는가(2026-09-14 확인):
    pykrx 1.2.8은 pandas<3.0을 요구하는데 이 저장소는 pandas==3.0.2다. 같은
    환경에 두면 pip이 에러 대신 pykrx를 1.0.51까지 조용히 낮추고, 그 버전에는
    KRX 로그인(auth) 기능이 아예 없어 모든 조회가 빈 응답으로 실패한다.
    그래서 scripts/fetch_kr_universe_pykrx.py를 별도 venv에서 돌려 JSON으로
    받아오고, 여기서는 그 파일만 읽는다.
    """
    path = Path(KR_UNIVERSE_FILE)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items") or []
    except Exception as e:
        logger.warning("KR 유니버스 파일 읽기 실패(%s: %s) — 다음 소스로 넘어감",
                       type(e).__name__, e)
        return []
    if not items:
        return []
    logger.info("KR 유니버스(pykrx 파일): %d 종목 (기준일 %s, 시총 하한 %s, pykrx %s)",
                len(items), payload.get("base_date"), payload.get("min_cap"),
                payload.get("pykrx_version"))
    return items


def get_kr_universe() -> list[dict]:
    """KR 유니버스. pykrx 파일 → 공공데이터포털 → pykrx 직접 → 정적 리스트 순.

    이력: 오랫동안 "공공데이터포털·pykrx 둘 다 GitHub Actions에서 IP 차단"으로
    적혀 있었으나 2026-09-14 실측 결과 그 진단은 틀렸다. pykrx 실패의 실제
    원인은 (1) pykrx 1.2.8이 KRX 로그인을 요구하는데 자격증명이 없었고,
    (2) pandas==3.0.2 핀 때문에 pip이 pykrx를 1.0.51로 조용히 낮춰 로그인
    기능 자체가 없는 버전이 깔린 것이었다. 격리 venv + KRX 계정으로
    GitHub Actions에서 코스피 943 / 코스닥 1822 전종목 조회에 성공했다.
    공공데이터포털은 여전히 0건이라 그쪽 진단은 미확인 상태로 남긴다."""
    universe = _kr_universe_from_file()
    if universe:
        return universe

    universe = _kr_universe_public_api()
    if universe:
        return universe
    logger.warning(
        "공공데이터포털 유니버스 수집 실패(DATA_GO_KR_API_KEY 미설정 또는 API 오류 — "
        "GitHub Actions에서는 apis.data.go.kr 자체가 연결 차단된 것으로 확인됨) "
        "— pykrx로 재시도."
    )

    universe = _kr_universe_pykrx()
    if universe:
        return universe
    logger.warning(
        "pykrx 직접 호출도 실패 — 정적 리스트로 폴백. "
        "이 프로세스의 pykrx는 pandas==3.0.2 핀 때문에 구버전(1.0.51)이 깔려 "
        "KRX 로그인 기능이 없다 — 정상 경로는 격리 venv가 만든 "
        f"{KR_UNIVERSE_FILE} 파일이며, 그게 없을 때만 여기까지 온다."
    )
    return _kr_universe_fallback()


# SPEC §6.1 — rate limit은 지수 백오프로 크게 기다린다(60초→180초→600초, 최대 3회).
# 그 외 에러는 데이터 자체가 없는 문제일 가능성이 높아 오래 기다려봐야 소용없으므로
# 기존처럼 짧게(2초)만 재시도한다.
RATE_LIMIT_BACKOFF = [60, 180, 600]


def fetch_financials_with_status(yf_symbol: str, retries: int = 2) -> tuple[dict | None, str]:
    """yfinance로 재무 데이터 수집. 실패 사유를 구분해서 반환한다.

    반환: (data 또는 None, ""|"rate_limited"|"no_data")
    """
    rate_limit_attempt = 0
    generic_attempt = 0
    while True:
        try:
            t = yf.Ticker(yf_symbol)
            info = t.info or {}

            # 기본 정보 없으면 스킵
            if not info.get("symbol") and not info.get("shortName"):
                return None, "no_data"

            fin = t.financials          # income statement (annual)
            bs  = t.balance_sheet       # balance sheet (annual)
            cf  = t.cashflow            # cash flow (annual)

            return {
                "info": info,
                "financials": fin,
                "balance_sheet": bs,
                "cashflow": cf,
            }, ""
        except Exception as e:
            if isinstance(e, YFRateLimitError):
                if rate_limit_attempt < len(RATE_LIMIT_BACKOFF):
                    wait = RATE_LIMIT_BACKOFF[rate_limit_attempt]
                    rate_limit_attempt += 1
                    logger.warning("%s: rate limit — %d초 대기 후 재시도 (%d/%d)",
                                   yf_symbol, wait, rate_limit_attempt, len(RATE_LIMIT_BACKOFF))
                    time.sleep(wait)
                    continue
                logger.debug("%s: rate limit 재시도 소진(%d회)", yf_symbol, len(RATE_LIMIT_BACKOFF))
                return None, "rate_limited"
            else:
                if generic_attempt < retries:
                    generic_attempt += 1
                    time.sleep(2)
                    continue
                logger.debug("재무 데이터 수집 실패 %s: %s", yf_symbol, e)
                return None, "no_data"


def fetch_financials(yf_symbol: str, retries: int = 2) -> dict | None:
    """yfinance로 재무 데이터 수집. 실패 시 None 반환 (하위 호환용 — 실패 사유가
    필요 없는 호출부는 이걸 그대로 쓴다. 사유가 필요하면
    fetch_financials_with_status()를 쓸 것)."""
    data, _ = fetch_financials_with_status(yf_symbol, retries)
    return data


def is_chinese_kr_listing(info: dict) -> bool:
    """한국 상장 중국기업 여부 판별."""
    country = (info.get("country") or "").lower()
    return country in ("china", "cn", "hong kong", "hk")


# SPEC §7 — 시가총액은 예산 회전(최대 10주)과 무관하게 매주 신선해야 유니버스
# 선별이 정확하다. 발행주식수(재무상태표, 이미 캐시됨)는 그대로 두고 가격만
# yf.download()로 배치 조회해서 종목당 개별 .info 호출 없이 갱신한다.
MARKET_CAP_BATCH_SIZE = 100
SHARES_OUTSTANDING_FIELDS = ("Ordinary Shares Number", "Share Issued")


def latest_shares_outstanding(balance_sheet: pd.DataFrame) -> float | None:
    """재무상태표 최신 회계기간(idx=0)의 발행주식수."""
    if balance_sheet is None or balance_sheet.empty:
        return None
    for field in SHARES_OUTSTANDING_FIELDS:
        if field not in balance_sheet.index:
            continue
        series = balance_sheet.loc[field].dropna()
        if not series.empty:
            return float(series.iloc[0])
    return None


def fetch_latest_prices_batch(yf_symbols: list[str], batch_size: int = MARKET_CAP_BATCH_SIZE) -> dict[str, float]:
    """다수 티커의 최신 종가를 yf.download()로 배치 조회한다 (SPEC §7).

    배치 호출도 rate limit 대상이라(SPEC §7 주의사항) §6.1과 동일한 백오프를
    적용한다. 배치 하나가 끝내 실패하면 그 배치의 종목들은 결과에서 빠지고
    (호출부가 직전 캐시 시가총액으로 대체), 나머지 배치는 계속 시도한다.

    단, 배치 하나가 rate limit 백오프(최대 840초)를 전부 소진하면 이후 배치는
    재시도 없이 즉시 건너뛴다 — 590종목 기준 최대 6배치 전부가 이 상황이면
    840초×6=84분이 걸려 그것만으로 GitHub Actions 90분 제한을 위협한다
    (§6.1의 종목별 회로차단기와 같은 이유의 안전장치, SPEC엔 없음).
    """
    prices: dict[str, float] = {}
    if not yf_symbols:
        return prices

    rate_limited_this_run = False
    for i in range(0, len(yf_symbols), batch_size):
        chunk = yf_symbols[i:i + batch_size]

        if rate_limited_this_run:
            logger.warning("이전 배치가 rate limit로 소진됨 — %d번째 배치는 재시도 없이 건너뜀",
                            i // batch_size)
            continue

        df = None
        rate_limit_attempt = 0
        while True:
            try:
                df = yf.download(chunk, period="5d", progress=False, group_by="ticker", threads=True)
                break
            except Exception as e:
                if isinstance(e, YFRateLimitError) and rate_limit_attempt < len(RATE_LIMIT_BACKOFF):
                    wait = RATE_LIMIT_BACKOFF[rate_limit_attempt]
                    rate_limit_attempt += 1
                    logger.warning("시가총액 가격 배치 조회 rate limit — %d초 대기 후 재시도 (%d/%d)",
                                   wait, rate_limit_attempt, len(RATE_LIMIT_BACKOFF))
                    time.sleep(wait)
                    continue
                if isinstance(e, YFRateLimitError):
                    rate_limited_this_run = True
                logger.warning("시가총액 가격 배치 조회 실패(%d개 종목, %d번째 배치): %s",
                                len(chunk), i // batch_size, e)
                df = None
                break

        if df is None or df.empty:
            continue

        for sym in chunk:
            try:
                closes = df[sym]["Close"].dropna()
                if not closes.empty:
                    prices[sym] = float(closes.iloc[-1])
            except (KeyError, TypeError):
                continue

    return prices


# SPEC엔 없는 안전장치(2026-08-31 상의 후 추가): 연속으로 이만큼 rate_limited가
# 나오면 "이번 실행은 야후 세션 전체가 막혔다"고 판단하고, 남은 예산 종목은
# 재시도 없이 바로 캐시로 돌린다. 없으면 예산 60종목이 전부 막힌 상황에서
# 종목당 최대 840초(60+180+600) 재시도를 반복해 GitHub Actions 90분 제한을
# 훌쩍 넘길 수 있다.
CIRCUIT_BREAKER_THRESHOLD = 3


def _new_run_state() -> dict:
    """collect_universe() 한 번의 실행에 걸쳐 공유되는 상태 — 회로차단기 +
    캐시 폴백 통계(§6.3의 "캐시 적중률" 경고에 씀)."""
    return {
        "consecutive_rate_limited": 0,
        "circuit_tripped": False,
        "live_ok": 0,
        "cache_fallback": 0,
        "no_data_at_all": 0,
    }


def _fetch_and_cache(conn, item: dict, run_state: dict) -> dict | None:
    """라이브로 재무 데이터를 받아오고, 성공/실패 여부와 무관하게 즉시
    fetch_status·fundamentals_cache에 기록한다 (SPEC §3 — 예산에 든 종목만
    이 경로를 탄다). 라이브가 실패하면 캐시로 폴백한다(SPEC §6.3) — 캐시도
    없으면 그 종목만 None(트랩 필터가 데이터부족으로 분류)."""
    if run_state["circuit_tripped"]:
        cached = get_cached_financials(conn, item["symbol"])
        if cached is not None:
            run_state["cache_fallback"] += 1
        else:
            run_state["no_data_at_all"] += 1
        return cached

    data, reason = fetch_financials_with_status(item["yf_symbol"])
    # KR: .KS가 실패했거나 "반쪽 응답"(코스닥 종목을 .KS로 조회하면
    # 재무제표는 오지만 시총·섹터가 비어 옴)이면 코스닥(.KQ)으로 재시도
    needs_kq_retry = (
        item["market"] == "KR"
        and item["yf_symbol"].endswith(".KS")
        and (data is None or not data["info"].get("marketCap"))
    )
    if needs_kq_retry:
        kq_symbol = item["yf_symbol"].replace(".KS", ".KQ")
        kq_data, kq_reason = fetch_financials_with_status(kq_symbol)
        if kq_data is not None and kq_data["info"].get("marketCap"):
            data, reason = kq_data, ""
            item["yf_symbol"] = kq_symbol
            item["exchange"] = "KOSDAQ"

    if reason == "rate_limited":
        run_state["consecutive_rate_limited"] += 1
        if run_state["consecutive_rate_limited"] >= CIRCUIT_BREAKER_THRESHOLD:
            run_state["circuit_tripped"] = True
            logger.warning("연속 %d종목 rate limit — 이번 실행 나머지는 재시도 없이 캐시로 전환",
                            run_state["consecutive_rate_limited"])
    else:
        run_state["consecutive_rate_limited"] = 0

    now = datetime.utcnow().isoformat()
    if data is None:
        upsert_fetch_status(conn, item["symbol"], item["market"], now, status=reason or "no_data")
        conn.commit()
        cached = get_cached_financials(conn, item["symbol"])
        if cached is not None:
            logger.warning("%s: 라이브 실패(%s) — 캐시로 대체", item["symbol"], reason)
            run_state["cache_fallback"] += 1
        else:
            run_state["no_data_at_all"] += 1
        return cached

    upsert_statement_rows(conn, item["symbol"], item["market"], "income", data["financials"], now)
    upsert_statement_rows(conn, item["symbol"], item["market"], "balance", data["balance_sheet"], now)
    upsert_statement_rows(conn, item["symbol"], item["market"], "cashflow", data["cashflow"], now)
    upsert_fetch_status(conn, item["symbol"], item["market"], now, status="ok", info=data["info"], success_at=now)
    conn.commit()
    run_state["live_ok"] += 1
    return data


TICKER_SLEEP_SEC = float(os.getenv("TICKER_SLEEP_SEC", "1.0"))  # SPEC §6.2


def collect_universe(markets: list[str] = ("US", "KR"), refresh_budget: int | None = None) -> tuple[list[dict], dict]:
    """전체 유니버스 수집 + 재무 데이터 포함.

    refresh_budget을 주면 SPEC §3 예산제가 적용된다 — fetch_status 우선순위
    (rate_limited 우선 → last_success_at 오래된 순)로 상위 refresh_budget개만
    야후에서 실제로 갱신(하고 캐시에 기록)하고, 나머지는 캐시에 저장된 값을
    그대로 읽는다(라이브 호출 없음). None이면 전부 라이브로 조회한다.

    반환: (결과 리스트, run_state) — run_state에는 이번 실행의 라이브 성공/
    캐시 폴백/완전 실패 건수와 회로차단기 작동 여부가 들어있다. 호출부가
    이걸로 "캐시 적중률이 낮으면 경고"(SPEC §6.3) 판단을 한다.
    """
    items = []
    if "US" in markets:
        items += get_us_universe()
    if "KR" in markets:
        items += get_kr_universe()

    conn = get_db()
    ensure_schema(conn)
    run_state = _new_run_state()

    if refresh_budget is not None:
        to_refresh, to_cache = select_refresh_targets(conn, items, refresh_budget)
        refresh_keys = {(it["market"], it["symbol"]) for it in to_refresh}
        # 캐시 대상 전체를 여기서 한꺼번에 읽어둔다 — 종목마다 개별 조회하면
        # Turso 왕복이 그만큼 쌓여 실측 약 7분이 추가로 걸렸다(2026-08-31).
        cache_lookup = get_cached_financials_bulk(conn, [it["symbol"] for it in to_cache])
        logger.info("총 유니버스: %d 종목 — 이번 주 갱신 %d / 캐시 사용 %d",
                    len(items), len(to_refresh), len(to_cache))
    else:
        refresh_keys = None
        cache_lookup = {}
        logger.info("총 유니버스: %d 종목 (예산제 미적용 — 전부 라이브 조회)", len(items))

    # SPEC §7 — 시가총액은 예산 회전과 무관하게 매주 신선해야 한다. 발행주식수는
    # 캐시된 재무상태표에서 읽고, 가격만 전 종목 배치로 새로 받는다.
    price_lookup = fetch_latest_prices_batch([it["yf_symbol"] for it in items])
    logger.info("시가총액용 가격 배치 조회: %d/%d 종목 성공", len(price_lookup), len(items))

    result = []
    for i, item in enumerate(items):
        if i % 50 == 0:
            logger.info("진행: %d / %d", i, len(items))

        use_live = refresh_keys is None or (item["market"], item["symbol"]) in refresh_keys
        data = _fetch_and_cache(conn, item, run_state) if use_live else cache_lookup.get(item["symbol"])

        if data is None:
            continue

        # 한국 상장 중국기업 제외
        if item["market"] == "KR" and is_chinese_kr_listing(data["info"]):
            logger.debug("한국상장중국기업 제외: %s", item["symbol"])
            continue

        # 시가총액 필터 — 배치로 받은 최신 가격 × 캐시된 발행주식수로 계산해
        # 예산 회전과 무관하게 매주 신선한 값을 쓴다(SPEC §7). 가격 배치 조회가
        # 실패했거나 발행주식수를 못 구하면 직전 캐시 시가총액(info.marketCap)으로
        # 대체.
        shares = latest_shares_outstanding(data.get("balance_sheet"))
        price = price_lookup.get(item["yf_symbol"])
        if price and shares:
            cap = price * shares
        else:
            cap = data["info"].get("marketCap") or 0
            logger.debug("%s: 배치 가격/발행주식수 없음 — 직전 캐시 시가총액으로 대체", item["symbol"])

        if item["market"] == "US":
            if cap < US_MIN_CAP:
                continue
            item["market_cap"] = cap
        elif "market_cap" not in item:
            item["market_cap"] = cap

        item["name"] = item.get("name") or data["info"].get("shortName") or item["symbol"]
        item["sector"] = data["info"].get("sector") or data["info"].get("industry") or "Unknown"
        item["financials_data"] = data

        result.append(item)
        if use_live and not run_state["circuit_tripped"]:
            time.sleep(TICKER_SLEEP_SEC)  # rate limiting — 캐시 읽기·회로차단 중엔 호출이 없으니 안 쉼

    if refresh_budget is not None:
        logger.info("이번 주 갱신 결과 — 라이브 성공 %d / 캐시 폴백 %d / 완전 실패 %d (회로차단기 작동: %s)",
                    run_state["live_ok"], run_state["cache_fallback"], run_state["no_data_at_all"],
                    run_state["circuit_tripped"])
    logger.info("재무 데이터 수집 완료: %d 종목", len(result))
    return result, run_state
