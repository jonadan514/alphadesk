"""Phase 0: 재무제표 캐시 스키마 + 읽기/쓰기 함수.

SPEC: docs/radar/SPEC_fundamentals_cache.md §2, §4
"""
from __future__ import annotations

import json
import math

import pandas as pd

FUNDAMENTALS_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS fundamentals_cache (
  ticker      TEXT NOT NULL,
  market      TEXT NOT NULL,
  statement   TEXT NOT NULL,
  period_end  TEXT NOT NULL,
  data        TEXT NOT NULL,
  fetched_at  TEXT NOT NULL,
  PRIMARY KEY (ticker, statement, period_end)
)
"""

FUNDAMENTALS_CACHE_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_fund_ticker ON fundamentals_cache(ticker)
"""

# status: 'ok' | 'rate_limited' | 'no_data' (SPEC §2.2).
# rate_limited은 §6(실패 내성)에서 지수 백오프 재시도와 함께 제대로 구분할
# 예정이라, 이번 백필에서는 실패를 전부 'no_data'로만 기록한다 — 원인 구분 없이
# "일단 못 받았다"만 남기는 의도적 단순화.
#
# info_payload: SPEC 원안에는 없는 확장 컬럼. 트랩 필터의 regime_fit 판정·
# 시가총액 필터·섹터·중국기업 판별이 재무제표가 아니라 yfinance `.info` 스냅샷에
# 의존하는데, 이걸 캐시하지 않으면 재무제표를 캐시해도 종목당 `.info` 라이브 호출이
# 매주 그대로 남아 호출량 감소 목표(10분의 1)를 절반만 달성하게 된다.
# (2026-08-28, 대화로 결정)
FETCH_STATUS_DDL = """
CREATE TABLE IF NOT EXISTS fetch_status (
  ticker           TEXT PRIMARY KEY,
  market           TEXT NOT NULL,
  last_attempt_at  TEXT,
  last_success_at  TEXT,
  status           TEXT,
  fail_count       INTEGER DEFAULT 0,
  info_payload     TEXT
)
"""


def ensure_schema(conn) -> None:
    conn.execute(FUNDAMENTALS_CACHE_DDL)
    conn.execute(FUNDAMENTALS_CACHE_INDEX_DDL)
    conn.execute(FETCH_STATUS_DDL)
    conn.commit()


def _json_safe(value):
    """numpy/pandas 스칼라 → JSON 직렬화 가능한 값. NaN/Infinity는 버린다(None).

    bool은 int의 서브클래스라 isinstance(value, (int, float)) 체크를 먼저 하면
    True/False가 1.0/0.0으로 바뀐다 — yfinance .info에 실제 bool 필드가
    있어(tradeable, hasPrePostMarketData 등) 반드시 먼저 걸러낸다.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    return value


def upsert_statement_rows(conn, ticker: str, market: str, statement: str,
                           df: pd.DataFrame, fetched_at: str) -> int:
    """DataFrame의 각 컬럼(회계기간)을 fundamentals_cache 한 행씩으로 저장.

    과거 행은 절대 덮어쓰지 않는다(INSERT OR IGNORE) — 같은
    (ticker, statement, period_end)에 이미 값이 있으면 조용히 건너뛴다.
    재실행해도 안전(멱등적)하다는 뜻이며, 동시에 백필을 몇 번 다시 돌려도
    첫 번째로 저장된 값이 계속 남는다는 뜻이기도 하다.

    반환값은 시도한 회계기간(컬럼) 수 — Turso 클라이언트가 rowcount를 주지 않아
    실제 신규삽입/스킵 구분은 하지 않는다(정보용 로그 카운트라 정확도가 중요하지
    않음).
    """
    if df is None or df.empty:
        return 0
    attempted = 0
    for col in df.columns:
        period_end = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
        series = df[col].dropna()
        if series.empty:
            continue
        row_data = {str(k): _json_safe(v) for k, v in series.items()}
        payload = json.dumps(row_data, ensure_ascii=False)
        conn.execute(
            """
            INSERT OR IGNORE INTO fundamentals_cache
              (ticker, market, statement, period_end, data, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticker, market, statement, period_end, payload, fetched_at),
        )
        attempted += 1
    return attempted


def upsert_fetch_status(conn, ticker: str, market: str, attempt_at: str, status: str,
                         info: dict | None = None, success_at: str | None = None) -> None:
    """종목별 수집 상태 갱신. 성공 시 info_payload도 함께 저장하고 fail_count를 0으로
    되돌린다. 실패 시 last_success_at은 건드리지 않고(COALESCE) fail_count만 늘린다."""
    info_payload = None
    if info:
        safe_info = {k: _json_safe(v) for k, v in info.items()}
        info_payload = json.dumps(safe_info, ensure_ascii=False, default=str)

    conn.execute(
        """
        INSERT INTO fetch_status
          (ticker, market, last_attempt_at, last_success_at, status, fail_count, info_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            market          = excluded.market,
            last_attempt_at = excluded.last_attempt_at,
            last_success_at = COALESCE(excluded.last_success_at, fetch_status.last_success_at),
            status          = excluded.status,
            fail_count      = CASE WHEN excluded.status = 'ok' THEN 0
                                    ELSE COALESCE(fetch_status.fail_count, 0) + 1 END,
            info_payload    = COALESCE(excluded.info_payload, fetch_status.info_payload)
        """,
        (ticker, market, attempt_at, success_at, status, 0 if status == "ok" else 1, info_payload),
    )


_STATEMENT_TO_KEY = {"income": "financials", "balance": "balance_sheet", "cashflow": "cashflow"}


def get_cached_financials(conn, ticker: str) -> dict | None:
    """fundamentals_cache + fetch_status에서 watchlist_collector.fetch_financials()와
    동일한 shape({"info", "financials", "balance_sheet", "cashflow"})로 재구성한다.

    트랩 필터가 라이브 호출로 받은 데이터와 캐시에서 재구성한 데이터를 구분 없이
    똑같이 다룰 수 있어야 하므로, 컬럼(회계기간)도 yfinance 관례대로 최신이
    idx=0이 되게 내림차순 정렬한다.

    캐시에 아무 것도 없으면(재무제표도 info도 없음) None.
    """
    rows = conn.execute(
        "SELECT statement, period_end, data FROM fundamentals_cache WHERE ticker = ?",
        (ticker,),
    ).fetchall()
    status_row = conn.execute(
        "SELECT info_payload FROM fetch_status WHERE ticker = ?",
        (ticker,),
    ).fetchone()

    if not rows and not (status_row and status_row[0]):
        return None

    info: dict = {}
    if status_row and status_row[0]:
        try:
            info = json.loads(status_row[0])
        except (TypeError, ValueError):
            info = {}

    by_statement: dict[str, dict[str, dict]] = {"income": {}, "balance": {}, "cashflow": {}}
    for statement, period_end, data in rows:
        if statement not in by_statement:
            continue
        try:
            by_statement[statement][period_end] = json.loads(data)
        except (TypeError, ValueError):
            continue

    def _to_df(period_dict: dict[str, dict]) -> pd.DataFrame:
        if not period_dict:
            return pd.DataFrame()
        cols_desc = sorted(period_dict.keys(), reverse=True)  # 최신 회계기간이 idx=0
        return pd.DataFrame({pd.Timestamp(c): pd.Series(period_dict[c]) for c in cols_desc})

    return {
        "info": info,
        "financials": _to_df(by_statement["income"]),
        "balance_sheet": _to_df(by_statement["balance"]),
        "cashflow": _to_df(by_statement["cashflow"]),
    }
