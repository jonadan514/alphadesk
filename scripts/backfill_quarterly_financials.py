"""Phase A-4: 승인된 테마 매핑 종목의 분기 매출 데이터 백필.

SPEC: docs/radar/SPEC_phase_a_signals.md §3.1
fundamentals_cache는 원래 연간 재무제표만 캐시한다(Phase 0). 실적 축의
"가속도"(g_t > g_t-1) 계산에는 분기 데이터가 필요한데, 전체 유니버스
(590종목)가 아니라 지금 테마에 승인된 종목만 좁혀서 백필한다 - Phase A는
미국만 다루므로 US 종목만 대상(사용자 결정, 옵션 2: 전체 유니버스 캐시
확장보다 필요한 범위만).

기존 주간 유니버스 갱신의 fetch_status는 건드리지 않는다 - 연간/분기
데이터는 신선도 주기가 다르고, fetch_status를 공유하면 주간 예산제 선정
로직(select_refresh_targets)이 "이미 갱신됐다"고 착각할 위험이 있다.

Usage:
  python scripts/backfill_quarterly_financials.py
"""
from __future__ import annotations

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


def get_approved_us_tickers(conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM theme_members WHERE approved = 1 AND market = 'US'"
    ).fetchall()
    return sorted(r[0] for r in rows)


def fetch_quarterly_financials(ticker: str, retries: int = 2):
    """반환: (DataFrame 또는 None, ""|"rate_limited"|"no_data")."""
    rate_limit_attempt = 0
    generic_attempt = 0
    while True:
        try:
            df = yf.Ticker(ticker).quarterly_financials
            if df is None or df.empty:
                return None, "no_data"
            return df, ""
        except Exception as e:
            if isinstance(e, YFRateLimitError):
                if rate_limit_attempt < len(RATE_LIMIT_BACKOFF):
                    wait = RATE_LIMIT_BACKOFF[rate_limit_attempt]
                    rate_limit_attempt += 1
                    _log(f"  {ticker}: rate limit - {wait}초 대기 후 재시도 "
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
    conn = get_db()
    ensure_schema(conn)

    tickers = get_approved_us_tickers(conn)
    if not tickers:
        _log("승인된 US 테마 매핑 종목이 없음 - 먼저 Phase A-2 승인을 완료할 것")
        sys.exit(1)
    _log(f"대상 종목 {len(tickers)}개 (승인된 매핑, US)")

    stats = {"ok": 0, "no_data": 0, "rate_limited": 0}
    now = datetime.utcnow().isoformat()
    for i, ticker in enumerate(tickers):
        df, status = fetch_quarterly_financials(ticker)
        if df is None:
            stats[status] += 1
            _log(f"[{i + 1}/{len(tickers)}] {ticker}: 실패({status})")
        else:
            n = upsert_statement_rows(conn, ticker, "US", "income_quarterly", df, now)
            conn.commit()
            stats["ok"] += 1
            _log(f"[{i + 1}/{len(tickers)}] {ticker}: {n}개 분기 저장")
        time.sleep(TICKER_SLEEP_SEC)

    conn.close()
    _log(f"완료 - {stats}")


if __name__ == "__main__":
    main()
