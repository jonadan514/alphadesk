"""워치리스트 밸류 지표 채우기 (scripts/compute_watchlist_valuation.py).

계산 자체는 test_company_valuation.py가 이미 덮는다. 여기서 보는 건 스크립트가
운영 DB와 주고받는 부분이다:
  - Turso가 숫자를 문자열로 돌려줘도 시가총액 나눗셈이 죽지 않는가
  - PSR을 못 구한 종목을 3등분 분모에서 빼먹지 않는가(빼면 "3곳 미만" 기준이 달라진다)
  - 적자 기업의 PER을 0으로 뭉개지 않고 NULL로 두는가
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from compute_watchlist_valuation import ensure_columns, load_candidates, run
from src.analyzers.company_valuation import CHEAP, EXPENSIVE, MID
from src.db.quarterly_financials import ensure_schema as ensure_raw_schema, insert_quarter

# 실제 워치리스트 표와 같은 이름·타입만 추려 만든다(스크리닝 스크립트가 만드는 표는
# 컬럼이 훨씬 많지만 여기서 쓰는 건 market/symbol/market_cap뿐이다).
CANDIDATES_DDL = """CREATE TABLE watchlist_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  market TEXT NOT NULL, symbol TEXT NOT NULL, name TEXT, market_cap REAL
)"""

# 최근 4분기: 2026Q3, Q2, Q1, 2025Q4
RECENT_4Q = [(2026, 3), (2026, 2), (2026, 1), (2025, 4)]


def _seed(conn, symbol, market, market_cap, revenue_per_q, net_income_per_q=10.0, quarters=RECENT_4Q):
    conn.execute(
        "INSERT INTO watchlist_candidates (market, symbol, name, market_cap) VALUES (?, ?, ?, ?)",
        (market, symbol, f"{symbol} 주식회사", market_cap),
    )
    for year, quarter in quarters:
        insert_quarter(
            conn, symbol, market, year, quarter,
            {"revenue": revenue_per_q, "operating_income": 5.0,
             "net_income": net_income_per_q, "fs_div": "CFS"},
            source="test", currency="KRW", collected_at="2026-10-01T00:00:00",
        )


def _read(conn, market="KR"):
    rows = conn.execute(
        "SELECT symbol, psr, per, valuation_tier FROM watchlist_candidates WHERE market = ?",
        (market,),
    ).fetchall()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


@pytest.fixture
def db(turso_like_db):
    turso_like_db.execute(CANDIDATES_DDL)
    ensure_raw_schema(turso_like_db)
    ensure_columns(turso_like_db)
    return turso_like_db


def test_psr_per_written_and_tiered(db):
    # 매출 합은 각각 400 / 800 / 1600, 시가총액은 전부 4000 -> PSR 10 / 5 / 2.5
    _seed(db, "AAA", "KR", 4000.0, revenue_per_q=100.0)
    _seed(db, "BBB", "KR", 4000.0, revenue_per_q=200.0)
    _seed(db, "CCC", "KR", 4000.0, revenue_per_q=400.0)

    run(db, ["KR"])
    got = _read(db)

    assert got["CCC"][0] == pytest.approx(2.5)
    assert got["BBB"][0] == pytest.approx(5.0)
    assert got["AAA"][0] == pytest.approx(10.0)
    # 순이익 합 40, 시총 4000 -> PER 100
    assert got["AAA"][1] == pytest.approx(100.0)
    # 3종목이면 정확히 한 칸씩
    assert (got["CCC"][2], got["BBB"][2], got["AAA"][2]) == (CHEAP, MID, EXPENSIVE)


def test_market_cap_as_string_does_not_crash(db):
    """Turso는 숫자를 문자열로 돌려준다 - load_candidates()가 float으로 되돌려야 한다."""
    _seed(db, "AAA", "KR", 4000, revenue_per_q=100.0)   # INTEGER로 들어가 문자열로 돌아온다

    loaded = load_candidates(db, "KR")
    assert loaded == [{"symbol": "AAA", "market_cap": 4000.0}]

    run(db, ["KR"])
    assert _read(db)["AAA"][0] == pytest.approx(10.0)


def test_missing_quarters_leave_null_but_still_count_in_denominator(db):
    """분기가 비는 종목도 3등분 분모에 남는다 (원칙 4 - 데이터부족은 탈락이 아니다).

    PSR을 구한 종목이 2곳뿐이면 '3곳 미만'이라 **전체**가 등급 없음이어야 한다.
    데이터부족 종목을 분모에서 빼면 2곳만으로 싼/비싼을 나눠 버린다.
    """
    _seed(db, "AAA", "KR", 4000.0, revenue_per_q=100.0)
    _seed(db, "BBB", "KR", 4000.0, revenue_per_q=200.0)
    _seed(db, "GAP", "KR", 4000.0, revenue_per_q=100.0,
          quarters=[(2026, 3), (2026, 2), (2025, 4), (2025, 3)])   # 2026Q1이 빔
    _seed(db, "NONE", "KR", None, revenue_per_q=100.0)             # 시가총액 없음

    run(db, ["KR"])
    got = _read(db)

    assert got["GAP"][0] is None and got["NONE"][0] is None
    assert all(v[2] is None for v in got.values())


def test_loss_making_company_gets_null_per_not_zero(db):
    """적자면 PER은 NULL. 0으로 넣으면 화면에서 'PER 0배'라는 거짓말이 된다."""
    _seed(db, "AAA", "KR", 4000.0, revenue_per_q=100.0, net_income_per_q=-10.0)
    _seed(db, "BBB", "KR", 4000.0, revenue_per_q=200.0, net_income_per_q=10.0)
    _seed(db, "CCC", "KR", 4000.0, revenue_per_q=400.0, net_income_per_q=10.0)

    run(db, ["KR"])
    got = _read(db)

    assert got["AAA"][1] is None
    assert got["AAA"][0] is not None   # 적자여도 PSR과 등급은 그대로 나온다
    assert got["AAA"][2] == EXPENSIVE


def test_other_market_untouched(db):
    """--market KR로 돌려도 US 행은 건드리지 않는다."""
    _seed(db, "AAA", "KR", 4000.0, revenue_per_q=100.0)
    _seed(db, "MSFT", "US", 4000.0, revenue_per_q=100.0)

    run(db, ["KR"])

    assert _read(db, "US")["MSFT"] == (None, None, None)
