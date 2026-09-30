"""기업별 분기 신호 저장 (분기 재설계 docs/REDESIGN_SPEC.md 5장).

테마 단위로 모으기 전의 회사별 계산 결과(변화 신호 3개 + 변화 기업 판정 + 밸류
위치)를 저장한다. compute_quarterly_classification.py는 지금까지 테마 집계
(financial_signal)만 내고 회사별 결과는 버렸는데, 그러면 화면의 "소속 기업 카드"
(SPEC 8장)를 만들 수 없고 "왜 이 테마가 켜졌는지"도 사람이 들여다볼 수 없다.

같은 회사가 여러 테마에 속할 수 있어 (theme_id, ticker, ...)를 기본키로 둔다.
변화 신호(매출 전환 등) 자체는 테마와 무관하게 같은 값이지만, 밸류 위치(3등분
등급)는 그 테마 소속 기업들 사이의 상대 순위라 테마마다 다를 수 있다. 같은 값을
소속 테마 개수만큼 중복 저장하는 비용보다, 화면이 "이 테마의 소속 기업"을 조인
없이 바로 조회하는 쪽을 택했다 - quarterly_theme_classification과 같은 판단이다.

upsert_company_signal()은 commit()을 하지 않는다(insert_quarter()와 같은 이유) -
테마 하나에 소속 기업이 많으면(KR 최대 30곳) 매번 커밋하면 Turso HTTP 왕복이
그만큼 쌓인다. 호출부가 테마·시장 단위로 한 번에 commit()한다.
"""
from __future__ import annotations

QUARTERLY_COMPANY_SIGNALS_DDL = """
CREATE TABLE IF NOT EXISTS quarterly_company_signals (
  theme_id             TEXT NOT NULL,
  ticker               TEXT NOT NULL,
  market               TEXT NOT NULL,
  fiscal_year          INTEGER NOT NULL,
  fiscal_quarter       INTEGER NOT NULL,
  revenue_transition   INTEGER,   -- 1/0/NULL(데이터부족) - 5-1
  revenue_flow         INTEGER,
  profit_transition    INTEGER,
  changed              INTEGER,   -- 변화 기업 판정 (5-2)
  revenue_recent       REAL,      -- 최근 분기 매출 (화면 표시용)
  revenue_year_ago     REAL,      -- 1년 전 같은 분기 매출
  psr                  REAL,      -- 5-4
  per                  REAL,      -- 흑자 기업만 값이 있다
  valuation_tier       TEXT,      -- '싼 편'/'중간'/'비싼 편'/NULL - 테마 안 상대 순위
  computed_at          TEXT NOT NULL,
  PRIMARY KEY (theme_id, ticker, market, fiscal_year, fiscal_quarter)
)
"""


def ensure_schema(conn) -> None:
    conn.execute(QUARTERLY_COMPANY_SIGNALS_DDL)
    conn.commit()


def _bit(value: bool | None) -> int | None:
    """bool|None -> 1/0/None. sqlite에는 bool이 없어 정수로 저장한다."""
    return None if value is None else int(bool(value))


def upsert_company_signal(conn, theme_id: str, ticker: str, market: str, year: int, quarter: int, *,
                          change: dict, psr: float | None, per: float | None,
                          tier: str | None, computed_at: str) -> None:
    """이 분기 이 테마 안에서 이 기업의 신호를 기록한다.

    change는 company_change_signals.change_company()의 반환값을 그대로 받는다 -
    revenue_transition/revenue_flow/profit_transition이 각각 {"pass": ...} 딕셔너리이거나
    (매출 전환이 데이터부족이면) None이다.
    """
    rt = change.get("revenue_transition") or {}
    rf = change.get("revenue_flow") or {}
    pt = change.get("profit_transition") or {}
    conn.execute(
        """
        INSERT INTO quarterly_company_signals
          (theme_id, ticker, market, fiscal_year, fiscal_quarter,
           revenue_transition, revenue_flow, profit_transition, changed,
           revenue_recent, revenue_year_ago, psr, per, valuation_tier, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(theme_id, ticker, market, fiscal_year, fiscal_quarter) DO UPDATE SET
          revenue_transition = excluded.revenue_transition,
          revenue_flow = excluded.revenue_flow,
          profit_transition = excluded.profit_transition,
          changed = excluded.changed,
          revenue_recent = excluded.revenue_recent,
          revenue_year_ago = excluded.revenue_year_ago,
          psr = excluded.psr,
          per = excluded.per,
          valuation_tier = excluded.valuation_tier,
          computed_at = excluded.computed_at
        """,
        (theme_id, ticker, market, year, quarter,
         _bit(rt.get("pass")), _bit(rf.get("pass")), _bit(pt.get("pass")), _bit(change.get("changed")),
         rt.get("recent"), rt.get("year_ago"), psr, per, tier, computed_at),
    )


_ROW_COLS = ("ticker", "fiscal_year", "fiscal_quarter", "revenue_transition", "revenue_flow",
             "profit_transition", "changed", "revenue_recent", "revenue_year_ago", "psr", "per",
             "valuation_tier", "computed_at")
_INT_COLS = ("fiscal_year", "fiscal_quarter")
_FLOAT_COLS = ("revenue_recent", "revenue_year_ago", "psr", "per")
_BOOL_COLS = ("revenue_transition", "revenue_flow", "profit_transition", "changed")


def _coerce(rec: dict) -> dict:
    """Turso HTTP는 INTEGER를 문자열로 돌려준다 - 읽을 때 한 번 실제 타입으로 되돌린다."""
    out = dict(rec)
    for key in _INT_COLS:
        if out.get(key) is not None:
            out[key] = int(out[key])
    for key in _FLOAT_COLS:
        if out.get(key) is not None:
            out[key] = float(out[key])
    for key in _BOOL_COLS:
        if out.get(key) is not None:
            out[key] = bool(int(out[key]))
    return out


def get_theme_company_signals(conn, theme_id: str, market: str, year: int, quarter: int) -> list[dict]:
    """이 테마·분기의 소속 기업 신호 전부, 티커 순."""
    rows = conn.execute(
        f"SELECT {', '.join(_ROW_COLS)} FROM quarterly_company_signals "
        "WHERE theme_id = ? AND market = ? AND fiscal_year = ? AND fiscal_quarter = ? "
        "ORDER BY ticker",
        (theme_id, market, year, quarter),
    ).fetchall()
    return [_coerce(dict(zip(_ROW_COLS, r))) for r in rows]
