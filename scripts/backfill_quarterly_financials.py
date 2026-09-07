"""Phase A-4/B-2: 승인된 테마 매핑 종목의 분기 매출 데이터 백필.

SPEC: docs/radar/SPEC_phase_a_signals.md §3.1
fundamentals_cache는 원래 연간 재무제표만 캐시한다(Phase 0). 실적 축의
"가속도"(g_t > g_t-1) 계산에는 분기 데이터가 필요한데, 전체 유니버스
(590종목)가 아니라 지금 테마에 승인된 종목만 좁혀서 백필한다(사용자 결정,
옵션 2: 전체 유니버스 캐시 확장보다 필요한 범위만). Phase A는 미국만
다뤘으나, Phase B에서 한국도 같은 방식으로 추가한다 - 한국 티커는 캐시
키(theme_members.ticker)는 접미사 없는 6자리 코드지만 yfinance 조회는
거래소 접미사가 필요해서, watchlist_collector.py와 동일한 관례로
".KS" 우선 조회 후 실패하면 ".KQ"로 재시도한다.

기존 주간 유니버스 갱신의 fetch_status는 건드리지 않는다 - 연간/분기
데이터는 신선도 주기가 다르고, fetch_status를 공유하면 주간 예산제 선정
로직(select_refresh_targets)이 "이미 갱신됐다"고 착각할 위험이 있다.

Usage:
  python scripts/backfill_quarterly_financials.py              # US+KR 둘 다
  python scripts/backfill_quarterly_financials.py --market KR   # 한쪽만
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.fundamentals_cache import ensure_schema, upsert_statement_rows

RATE_LIMIT_BACKOFF = [60, 180, 600]
TICKER_SLEEP_SEC = 1.0


def _log(msg: str) -> None:
    print(f"[quarterly] {msg}")


def get_approved_tickers(conn, market: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM theme_members WHERE approved = 1 AND market = ?",
        (market,),
    ).fetchall()
    return sorted(r[0] for r in rows)


def yf_symbol_candidates(ticker: str, market: str) -> list[str]:
    """야후 파이낸스 조회용 심볼 후보 - 실패하면 순서대로 다음 걸 시도한다.
    US는 캐시 키와 yfinance 심볼이 동일. KR은 코스피(.KS) 우선, 안 되면
    코스닥(.KQ) - watchlist_collector.py의 기존 관례와 동일."""
    if market != "KR":
        return [ticker]
    return [f"{ticker}.KS", f"{ticker}.KQ"]


def fetch_quarterly_financials(yf_symbol: str, retries: int = 2):
    """반환: (DataFrame 또는 None, ""|"rate_limited"|"no_data")."""
    rate_limit_attempt = 0
    generic_attempt = 0
    while True:
        try:
            df = yf.Ticker(yf_symbol).quarterly_financials
            if df is None or df.empty:
                return None, "no_data"
            return df, ""
        except Exception as e:
            if isinstance(e, YFRateLimitError):
                if rate_limit_attempt < len(RATE_LIMIT_BACKOFF):
                    wait = RATE_LIMIT_BACKOFF[rate_limit_attempt]
                    rate_limit_attempt += 1
                    _log(f"  {yf_symbol}: rate limit - {wait}초 대기 후 재시도 "
                         f"({rate_limit_attempt}/{len(RATE_LIMIT_BACKOFF)})")
                    time.sleep(wait)
                    continue
                return None, "rate_limited"
            else:
                if generic_attempt < retries:
                    generic_attempt += 1
                    time.sleep(2)
                    continue
                return None, "no_data"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["US", "KR"], default=None,
                         help="비우면 US+KR 둘 다")
    args = parser.parse_args()
    markets = [args.market] if args.market else ["US", "KR"]

    conn = get_db()
    ensure_schema(conn)

    overall = {"ok": 0, "no_data": 0, "rate_limited": 0}
    for market in markets:
        tickers = get_approved_tickers(conn, market)
        if not tickers:
            _log(f"{market}: 승인된 테마 매핑 종목이 없음 - 건너뜀")
            continue
        _log(f"{market}: 대상 종목 {len(tickers)}개 (승인된 매핑)")

        stats = {"ok": 0, "no_data": 0, "rate_limited": 0}
        now = datetime.utcnow().isoformat()
        for i, ticker in enumerate(tickers):
            df, status = None, "no_data"
            for yf_symbol in yf_symbol_candidates(ticker, market):
                df, status = fetch_quarterly_financials(yf_symbol)
                if df is not None or status == "rate_limited":
                    break  # 성공했거나, rate limit이면 다음 접미사도 어차피 막힘
            if df is None:
                stats[status] += 1
                _log(f"[{market} {i + 1}/{len(tickers)}] {ticker}: 실패({status})")
            else:
                n = upsert_statement_rows(conn, ticker, market, "income_quarterly", df, now)
                conn.commit()
                stats["ok"] += 1
                _log(f"[{market} {i + 1}/{len(tickers)}] {ticker}: {n}개 분기 저장")
            time.sleep(TICKER_SLEEP_SEC)

        _log(f"{market} 완료 - {stats}")
        for k in overall:
            overall[k] += stats[k]

    conn.close()
    _log(f"전체 완료 - {overall}")


if __name__ == "__main__":
    main()
