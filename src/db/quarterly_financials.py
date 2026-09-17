"""분기 재무 원본값 저장 (분기 재설계 docs/REDESIGN_SPEC.md 4-4).

기업 x 분기 단위로 매출·영업이익·순이익 원본값만 둔다. 변화 신호 같은 계산값은 따로 둔다.
각 행에 출처(DART/yfinance), 연결/별도 구분, 계산 방식(보고값/4분기 계산), 수집일을 남긴다.

덮어쓰지 않는다(원칙 5). 같은 분기를 다시 수집하면 **비어 있던 칸만 채운다** - 처음에
4분기를 계산할 수 없어 비워뒀다가 나중에 3분기 누적값이 들어와 계산되는 경우를 위해서다.
이미 있는 값은 바꾸지 않는다(정정공시로 값이 바뀌었는지는 별도 점검 대상).
"""
from __future__ import annotations

QUARTERLY_FINANCIALS_DDL = """
CREATE TABLE IF NOT EXISTS quarterly_financials (
  ticker           TEXT NOT NULL,
  market           TEXT NOT NULL,
  fiscal_year      INTEGER NOT NULL,
  fiscal_quarter   INTEGER NOT NULL,
  revenue          REAL,
  operating_income REAL,
  net_income       REAL,
  source           TEXT NOT NULL,   -- 'DART' | 'yfinance'
  fs_div           TEXT,            -- 'CFS'(연결) | 'OFS'(별도) | NULL(yfinance)
  derived          TEXT,            -- 'reported' | 'annual_minus_9m'
  currency         TEXT,
  collected_at     TEXT NOT NULL,
  PRIMARY KEY (ticker, market, fiscal_year, fiscal_quarter)
)
"""


def ensure_schema(conn) -> None:
    conn.execute(QUARTERLY_FINANCIALS_DDL)
    conn.commit()


def upsert_quarter(conn, ticker: str, market: str, year: int, quarter: int, values: dict,
                   source: str, currency: str, collected_at: str) -> None:
    conn.execute(
        """
        INSERT INTO quarterly_financials
          (ticker, market, fiscal_year, fiscal_quarter, revenue, operating_income, net_income,
           source, fs_div, derived, currency, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, market, fiscal_year, fiscal_quarter) DO UPDATE SET
          revenue          = COALESCE(quarterly_financials.revenue, excluded.revenue),
          operating_income = COALESCE(quarterly_financials.operating_income, excluded.operating_income),
          net_income       = COALESCE(quarterly_financials.net_income, excluded.net_income),
          fs_div           = COALESCE(quarterly_financials.fs_div, excluded.fs_div),
          derived          = COALESCE(quarterly_financials.derived, excluded.derived)
        """,
        (ticker, market, year, quarter, values.get("revenue"), values.get("operating_income"),
         values.get("net_income"), source, values.get("fs_div"), values.get("derived"),
         currency, collected_at),
    )


def get_quarters(conn, ticker: str, market: str) -> list[dict]:
    rows = conn.execute(
        "SELECT fiscal_year, fiscal_quarter, revenue, operating_income, net_income, source, fs_div, derived "
        "FROM quarterly_financials WHERE ticker = ? AND market = ? "
        "ORDER BY fiscal_year DESC, fiscal_quarter DESC",
        (ticker, market),
    ).fetchall()
    keys = ("fiscal_year", "fiscal_quarter", "revenue", "operating_income", "net_income",
            "source", "fs_div", "derived")
    return [dict(zip(keys, r)) for r in rows]
