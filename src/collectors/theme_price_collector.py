"""Phase A-5: 테마 소속 기업 4주 수익률 배치 조회.

SPEC: docs/radar/SPEC_phase_a_signals.md §4
종목별 개별 호출 금지(§4.3, Phase 0 §7과 동일) - yf.download() 배치로 처리.
"""
from __future__ import annotations

import time

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

RATE_LIMIT_BACKOFF = [60, 180, 600]
BATCH_SIZE = 100
LOOKBACK_TRADING_DAYS = 20  # 4주 = 5거래일 x 4
MIN_TRADING_DAYS = LOOKBACK_TRADING_DAYS + 1  # 상장 4주 미만 제외(§4.3)


def compute_return_batch(tickers: list[str], batch_size: int = BATCH_SIZE) -> dict[str, float | None]:
    """4주(20거래일) 수익률을 배치로 계산한다.

    반환: {ticker: 수익률(float) 또는 None(제외 - 상장 4주 미만/거래정지/조회실패)}.
    인자로 준 모든 티커에 대해 키가 존재한다.

    날짜(금요일) 대신 거래일 개수(20)로 4주 전을 잡는다 - 공휴일 때문에
    "정확히 28일 전"을 날짜로 찾으면 어긋날 수 있어 더 안정적이다.
    """
    returns: dict[str, float | None] = {t: None for t in tickers}
    if not tickers:
        return returns

    rate_limited_this_run = False
    for i in range(0, len(tickers), batch_size):
        chunk = tickers[i:i + batch_size]
        if rate_limited_this_run:
            continue

        df = None
        rate_limit_attempt = 0
        while True:
            try:
                # 20거래일 + 휴장일 여유분 확보 - 45일이면 공휴일 섞여도 20거래일은 충분
                df = yf.download(chunk, period="45d", progress=False, group_by="ticker", threads=True)
                break
            except Exception as e:
                if isinstance(e, YFRateLimitError) and rate_limit_attempt < len(RATE_LIMIT_BACKOFF):
                    wait = RATE_LIMIT_BACKOFF[rate_limit_attempt]
                    rate_limit_attempt += 1
                    time.sleep(wait)
                    continue
                if isinstance(e, YFRateLimitError):
                    rate_limited_this_run = True
                df = None
                break

        if df is None or df.empty:
            continue

        for sym in chunk:
            try:
                # yf.download()는 인자가 리스트면(길이 1이어도) group_by="ticker"일 때
                # 항상 {티커: {필드: ...}} 형태의 MultiIndex 컬럼을 만든다.
                closes = df[sym]["Close"].dropna()
                if len(closes) < MIN_TRADING_DAYS:
                    continue  # 상장 4주 미만 - 제외하고 로그(호출부가 로그 남김)

                volumes = df[sym]["Volume"].reindex(closes.index)
                recent_vol = volumes.tail(3).fillna(0)
                if (recent_vol == 0).all():
                    continue  # 최근 연속 거래량 0 - 거래정지로 보고 제외(§4.3)

                current = float(closes.iloc[-1])
                prior = float(closes.iloc[-1 - LOOKBACK_TRADING_DAYS])
                if not prior:
                    continue
                returns[sym] = current / prior - 1
            except (KeyError, TypeError, IndexError):
                continue

    return returns
