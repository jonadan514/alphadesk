"""Phase 0: 재무제표 캐시 스키마 + 읽기/쓰기 함수.

SPEC: docs/radar/SPEC_fundamentals_cache.md §2, §3, §4
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


def _to_df(period_dict: dict[str, dict]) -> pd.DataFrame:
    if not period_dict:
        return pd.DataFrame()
    cols_desc = sorted(period_dict.keys(), reverse=True)  # 최신 회계기간이 idx=0
    return pd.DataFrame({pd.Timestamp(c): pd.Series(period_dict[c]) for c in cols_desc})


def _reconstruct(by_statement: dict[str, dict[str, dict]], info_payload: str | None) -> dict:
    """fetch_financials()와 동일한 shape({"info", "financials", "balance_sheet",
    "cashflow"})로 재구성 — 단일 조회(get_cached_financials)와 벌크 조회
    (get_cached_financials_bulk)가 공유하는 조립 로직.

    "financials_quarterly"는 Phase A-4(실적 축)를 위해 추가됨 - 연간
    재무제표만 있던 기존 캐시에 분기 재무제표(statement="income_quarterly")도
    선택적으로 들어올 수 있게 함. 기존 호출부는 이 키를 그냥 무시하면 되므로
    하위 호환에 영향 없음."""
    info: dict = {}
    if info_payload:
        try:
            info = json.loads(info_payload)
        except (TypeError, ValueError):
            info = {}
    return {
        "info": info,
        "financials": _to_df(by_statement.get("income", {})),
        "balance_sheet": _to_df(by_statement.get("balance", {})),
        "cashflow": _to_df(by_statement.get("cashflow", {})),
        "financials_quarterly": _to_df(by_statement.get("income_quarterly", {})),
    }


def get_cached_financials(conn, ticker: str) -> dict | None:
    """fundamentals_cache + fetch_status에서 watchlist_collector.fetch_financials()와
    동일한 shape로 재구성한다. 종목 하나만 필요할 때 쓴다 — 유니버스 전체를
    돌 때는 get_cached_financials_bulk()를 써서 Turso 왕복 횟수를 줄일 것.

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

    info_payload = status_row[0] if status_row else None
    if not rows and not info_payload:
        return None

    by_statement: dict[str, dict[str, dict]] = {"income": {}, "balance": {}, "cashflow": {}, "income_quarterly": {}}
    for statement, period_end, data in rows:
        if statement not in by_statement:
            continue
        try:
            by_statement[statement][period_end] = json.loads(data)
        except (TypeError, ValueError):
            continue

    return _reconstruct(by_statement, info_payload)


def get_cached_financials_bulk(conn, tickers: list[str]) -> dict[str, dict | None]:
    """get_cached_financials()를 여러 종목에 대해 한 번에 처리한다.

    Turso는 execute() 호출 한 번이 곧 HTTP 왕복 한 번이라, 종목마다 개별
    조회하면 그 횟수만큼 지연이 그대로 쌓인다 — 실측 결과 530종목을 개별
    조회하니 주간 파이프라인 실행 시간에 약 7분이 추가로 붙었다(2026-08-31).
    쿼리 횟수를 종목 수와 무관한 고정 횟수로 줄여서 이 비용을 없앤다.

    반환: {ticker: 재구성된 dict 또는 None(캐시 없음)}. 인자로 준 tickers의
    모든 항목에 대해 키가 존재한다.
    """
    if not tickers:
        return {}

    CHUNK = 200  # IN() 절 파라미터 수를 안전한 범위로 제한
    fund_by_ticker: dict[str, dict[str, dict[str, dict]]] = {}
    info_by_ticker: dict[str, str] = {}

    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i + CHUNK]
        placeholders = ",".join("?" for _ in chunk)

        for ticker, statement, period_end, data in conn.execute(
            f"SELECT ticker, statement, period_end, data FROM fundamentals_cache WHERE ticker IN ({placeholders})",
            chunk,
        ).fetchall():
            bucket = fund_by_ticker.setdefault(
                ticker, {"income": {}, "balance": {}, "cashflow": {}, "income_quarterly": {}}
            )
            if statement not in bucket:
                continue
            try:
                bucket[statement][period_end] = json.loads(data)
            except (TypeError, ValueError):
                continue

        for ticker, info_payload in conn.execute(
            f"SELECT ticker, info_payload FROM fetch_status WHERE ticker IN ({placeholders})",
            chunk,
        ).fetchall():
            if info_payload:
                info_by_ticker[ticker] = info_payload

    result: dict[str, dict | None] = {}
    for ticker in tickers:
        by_statement = fund_by_ticker.get(ticker)
        info_payload = info_by_ticker.get(ticker)
        if not by_statement and not info_payload:
            result[ticker] = None
        else:
            result[ticker] = _reconstruct(by_statement or {}, info_payload)
    return result


def select_refresh_targets(conn, universe: list[dict], budget: int) -> tuple[list[dict], list[dict]]:
    """유니버스를 (이번 주 라이브로 갱신할 것, 캐시를 그대로 쓸 것)으로 나눈다.

    SPEC §3 우선순위: rate_limited 상태 종목이 최우선, 그 다음은
    last_success_at 오래된 순 — 한 번도 성공한 적 없는 종목(fetch_status에
    행이 아예 없거나 last_success_at이 NULL인 경우)이 가장 먼저 오도록
    빈 문자열로 취급해 정렬한다(어떤 날짜 문자열보다 사전순으로 앞선다).

    universe의 각 항목은 최소 {"market", "symbol"}을 가져야 한다.
    """
    status_rows = conn.execute("SELECT ticker, status, last_success_at FROM fetch_status").fetchall()
    status_map = {row[0]: {"status": row[1], "last_success_at": row[2]} for row in status_rows}

    def priority_key(item: dict) -> tuple[int, str]:
        st = status_map.get(item["symbol"])
        if st and st["status"] == "rate_limited":
            return (0, "")
        return (1, (st["last_success_at"] if st else None) or "")

    ordered = sorted(universe, key=priority_key)
    return ordered[:budget], ordered[budget:]
