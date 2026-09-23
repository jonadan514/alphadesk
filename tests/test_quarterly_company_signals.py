"""기업별 분기 신호 저장 (docs/REDESIGN_SPEC.md 5장, src/db/quarterly_company_signals.py).

핵심: change_company()의 반환 모양(부분 데이터부족이면 하위 딕셔너리가 None)을 그대로
받아도 죽지 않아야 하고, 0(False)과 NULL(데이터부족)이 섞이면 안 된다.
"""
from __future__ import annotations

import pytest

from src.db.quarterly_company_signals import (ensure_schema, get_theme_company_signals,
                                               upsert_company_signal)

CHANGE_FULL = {
    "changed": True,
    "revenue_transition": {"pass": True, "recent": 130.0, "year_ago": 100.0, "reason": None},
    "revenue_flow": {"pass": True, "hits": 3, "reason": None},
    "profit_transition": {"pass": True, "reason": None},
}
CHANGE_NA = {   # 매출 전환이 데이터부족이면 change_company()는 나머지를 전부 None으로 채운다
    "changed": None,
    "revenue_transition": {"pass": None, "recent": None, "year_ago": None, "reason": "분기 재무 없음"},
    "revenue_flow": None,
    "profit_transition": None,
}


def _put(conn, theme_id="battery", ticker="005930", market="KR", year=2026, quarter=3,
        change=CHANGE_FULL, psr=2.5, per=15.0, tier="싼 편", at="2026-10-01T00:00:00"):
    upsert_company_signal(conn, theme_id, ticker, market, year, quarter,
                          change=change, psr=psr, per=per, tier=tier, computed_at=at)
    conn.commit()


def test_넣은_값을_그대로_읽는다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db)
    got = get_theme_company_signals(memory_db, "battery", "KR", 2026, 3)
    assert len(got) == 1
    row = got[0]
    assert row["changed"] is True
    assert row["revenue_transition"] is True and row["revenue_flow"] is True
    assert row["revenue_recent"] == 130.0 and row["revenue_year_ago"] == 100.0
    assert row["psr"] == 2.5 and row["per"] == 15.0 and row["valuation_tier"] == "싼 편"


def test_계산한_적_없으면_빈_목록이다(memory_db):
    ensure_schema(memory_db)
    assert get_theme_company_signals(memory_db, "battery", "KR", 2026, 3) == []


def test_매출전환이_데이터부족이면_나머지도_None으로_저장된다(memory_db):
    """change_company()가 revenue_flow/profit_transition을 통째로 None으로 주는 경우 -
    .get('pass')를 안전하게 다뤄야 한다(None.get이면 죽는다)."""
    ensure_schema(memory_db)
    _put(memory_db, change=CHANGE_NA, psr=None, per=None, tier=None)
    row = get_theme_company_signals(memory_db, "battery", "KR", 2026, 3)[0]
    assert row["changed"] is None
    assert row["revenue_transition"] is None and row["revenue_flow"] is None
    assert row["profit_transition"] is None
    assert row["psr"] is None and row["valuation_tier"] is None


def test_탈락은_None이_아니라_False로_저장된다(memory_db):
    change_fail = {
        "changed": False,
        "revenue_transition": {"pass": False, "recent": 90.0, "year_ago": 100.0, "reason": None},
        "revenue_flow": {"pass": False, "hits": 1, "reason": None},
        "profit_transition": {"pass": False, "reason": None},
    }
    ensure_schema(memory_db)
    _put(memory_db, change=change_fail)
    row = get_theme_company_signals(memory_db, "battery", "KR", 2026, 3)[0]
    assert row["changed"] is False and row["revenue_transition"] is False


def test_같은_회사가_여러_테마에_속하면_각각_저장된다(memory_db):
    """밸류 등급은 테마마다 다를 수 있다 - 같은 회사, 같은 분기, 다른 테마."""
    ensure_schema(memory_db)
    _put(memory_db, theme_id="battery", ticker="373220", tier="싼 편")
    _put(memory_db, theme_id="ev_value_chain", ticker="373220", tier="비싼 편")
    a = get_theme_company_signals(memory_db, "battery", "KR", 2026, 3)
    b = get_theme_company_signals(memory_db, "ev_value_chain", "KR", 2026, 3)
    assert a[0]["valuation_tier"] == "싼 편"
    assert b[0]["valuation_tier"] == "비싼 편"


def test_테마_안에서_티커순으로_돌려준다(memory_db):
    ensure_schema(memory_db)
    for t in ["373220", "005930", "000660"]:
        _put(memory_db, ticker=t)
    got = [r["ticker"] for r in get_theme_company_signals(memory_db, "battery", "KR", 2026, 3)]
    assert got == ["000660", "005930", "373220"]


def test_다른_분기_행은_건드리지_않는다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, year=2026, quarter=2, psr=1.0)
    _put(memory_db, year=2026, quarter=3, psr=2.0)
    q2 = get_theme_company_signals(memory_db, "battery", "KR", 2026, 2)[0]
    q3 = get_theme_company_signals(memory_db, "battery", "KR", 2026, 3)[0]
    assert q2["psr"] == 1.0 and q3["psr"] == 2.0


def test_같은_테마_같은_분기를_다시_계산하면_갱신된다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, tier="싼 편", at="2026-10-01T00:00:00")
    _put(memory_db, tier="비싼 편", at="2026-10-02T00:00:00")
    row = get_theme_company_signals(memory_db, "battery", "KR", 2026, 3)[0]
    assert row["valuation_tier"] == "비싼 편" and row["computed_at"] == "2026-10-02T00:00:00"


def test_다른_시장은_섞이지_않는다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, ticker="NVDA", market="US")
    _put(memory_db, ticker="005930", market="KR")
    us = get_theme_company_signals(memory_db, "battery", "US", 2026, 3)
    assert len(us) == 1 and us[0]["ticker"] == "NVDA"


# ── 운영 DB(Turso) 타입 ────────────────────────────────────────

def test_운영DB에서도_타입이_맞다(turso_like_db):
    ensure_schema(turso_like_db)
    _put(turso_like_db)
    row = get_theme_company_signals(turso_like_db, "battery", "KR", 2026, 3)[0]
    assert row["changed"] is True and isinstance(row["changed"], bool)
    assert row["fiscal_year"] == 2026 and isinstance(row["fiscal_year"], int)
    assert row["psr"] == 2.5 and isinstance(row["psr"], float)


def test_운영DB에서도_데이터부족이_None으로_남는다(turso_like_db):
    ensure_schema(turso_like_db)
    _put(turso_like_db, change=CHANGE_NA, psr=None, per=None, tier=None)
    row = get_theme_company_signals(turso_like_db, "battery", "KR", 2026, 3)[0]
    assert row["changed"] is None and row["psr"] is None
