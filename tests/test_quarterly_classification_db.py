"""테마 4칸 분류 이력 저장 (docs/REDESIGN_SPEC.md 7장, src/db/quarterly_classification.py).

핵심: 같은 분기는 다시 계산하면 갱신되고, 다른 분기 행은 건드리지 않는다(이력이 쌓인다).
데이터부족(None)은 sqlite에 NULL로 저장되고 0과 구분되어 그대로 돌아와야 한다.
"""
from __future__ import annotations

from src.db.quarterly_classification import (ensure_schema, get_classification,
                                              get_theme_history, previous_classification,
                                              upsert_classification)

FIN_ON = {"on": True, "changed": 3, "judged": 7, "ratio": 3 / 7}
FIN_OFF = {"on": False, "changed": 1, "judged": 7, "ratio": 1 / 7}
FIN_NA = {"on": None, "changed": 0, "judged": 1, "ratio": None}
NEWS_HIGH = {"high": True, "ratio": 2.1, "this_quarter": 300}
NEWS_LOW = {"high": False, "ratio": 0.8, "this_quarter": 90}
NEWS_NA = {"high": None, "ratio": None, "this_quarter": 40}


def _put(conn, theme_id="battery", market="KR", year=2026, quarter=3,
         financial=FIN_ON, news=NEWS_LOW, classification="조용한 변화", at="2026-10-01T00:00:00"):
    upsert_classification(conn, theme_id, market, year, quarter,
                          financial=financial, news=news, classification=classification,
                          computed_at=at)


def test_넣은_값을_그대로_읽는다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db)
    got = get_classification(memory_db, "battery", "KR", 2026, 3)
    assert got["financial_on"] is True and got["news_high"] is False
    assert got["classification"] == "조용한 변화"
    assert got["financial_changed"] == 3 and got["financial_judged"] == 7


def test_계산한_적_없으면_None이다(memory_db):
    ensure_schema(memory_db)
    assert get_classification(memory_db, "battery", "KR", 2026, 3) is None


def test_데이터부족은_0이_아니라_None으로_돌아온다(memory_db):
    """financial_on=False(0)와 financial_on=None(데이터부족)이 섞이면 안 된다."""
    ensure_schema(memory_db)
    _put(memory_db, financial=FIN_NA, news=NEWS_NA, classification=None)
    got = get_classification(memory_db, "battery", "KR", 2026, 3)
    assert got["financial_on"] is None and got["news_high"] is None
    assert got["classification"] is None


def test_꺼짐은_None이_아니라_False로_저장된다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, financial=FIN_OFF, news=NEWS_LOW, classification="관심 밖")
    got = get_classification(memory_db, "battery", "KR", 2026, 3)
    assert got["financial_on"] is False and got["news_high"] is False


def test_같은_분기를_다시_계산하면_갱신된다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, classification="조용한 변화", at="2026-10-01T00:00:00")
    _put(memory_db, financial=FIN_ON, news=NEWS_HIGH, classification="확인된 변화",
        at="2026-10-02T00:00:00")
    got = get_classification(memory_db, "battery", "KR", 2026, 3)
    assert got["classification"] == "확인된 변화" and got["computed_at"] == "2026-10-02T00:00:00"


def test_다른_분기_행은_건드리지_않는다(memory_db):
    """이력이 쌓인다 - 이번 분기를 갱신해도 지난 분기 값은 그대로다."""
    ensure_schema(memory_db)
    _put(memory_db, year=2026, quarter=2, classification="관심 밖")
    _put(memory_db, year=2026, quarter=3, classification="조용한 변화")
    assert get_classification(memory_db, "battery", "KR", 2026, 2)["classification"] == "관심 밖"
    assert get_classification(memory_db, "battery", "KR", 2026, 3)["classification"] == "조용한 변화"


def test_다른_테마_시장_분기는_섞이지_않는다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, theme_id="battery", market="KR", classification="조용한 변화")
    _put(memory_db, theme_id="battery", market="US", classification="관심 밖")
    _put(memory_db, theme_id="ai_semiconductor", market="KR", classification="확인된 변화")
    assert get_classification(memory_db, "battery", "KR", 2026, 3)["classification"] == "조용한 변화"
    assert get_classification(memory_db, "battery", "US", 2026, 3)["classification"] == "관심 밖"
    assert get_classification(memory_db, "ai_semiconductor", "KR", 2026, 3)["classification"] == "확인된 변화"


def test_테마_이력을_최신_분기부터_돌려준다(memory_db):
    ensure_schema(memory_db)
    for y, q in [(2025, 3), (2026, 1), (2025, 4), (2026, 2)]:
        _put(memory_db, year=y, quarter=q)
    got = [(r["fiscal_year"], r["fiscal_quarter"]) for r in get_theme_history(memory_db, "battery", "KR")]
    assert got == [(2026, 2), (2026, 1), (2025, 4), (2025, 3)]


def test_직전_분기_분류를_찾는다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, year=2026, quarter=2, classification="관심 밖")
    got = previous_classification(memory_db, "battery", "KR", 2026, 3)
    assert got["classification"] == "관심 밖"


def test_직전_분기가_연도를_넘어가도_찾는다(memory_db):
    ensure_schema(memory_db)
    _put(memory_db, year=2025, quarter=4, classification="기대 선행")
    got = previous_classification(memory_db, "battery", "KR", 2026, 1)
    assert got["classification"] == "기대 선행"


def test_직전_분기_기록이_없으면_None이다(memory_db):
    ensure_schema(memory_db)
    assert previous_classification(memory_db, "battery", "KR", 2026, 3) is None


# ── 운영 DB(Turso) 타입 ────────────────────────────────────────

def test_운영DB에서도_숫자와_불리언이_맞다(turso_like_db):
    ensure_schema(turso_like_db)
    _put(turso_like_db, financial=FIN_ON, news=NEWS_HIGH, classification="확인된 변화")
    got = get_classification(turso_like_db, "battery", "KR", 2026, 3)
    assert got["financial_on"] is True and isinstance(got["financial_on"], bool)
    assert got["news_high"] is True and isinstance(got["news_high"], bool)
    assert got["financial_changed"] == 3 and isinstance(got["financial_changed"], int)
    assert got["financial_ratio"] == 3 / 7 and isinstance(got["financial_ratio"], float)
    assert got["fiscal_year"] == 2026 and isinstance(got["fiscal_year"], int)


def test_운영DB에서도_데이터부족이_None으로_남는다(turso_like_db):
    ensure_schema(turso_like_db)
    _put(turso_like_db, financial=FIN_NA, news=NEWS_NA, classification=None)
    got = get_classification(turso_like_db, "battery", "KR", 2026, 3)
    assert got["financial_on"] is None and got["news_high"] is None and got["classification"] is None


def test_운영DB에서도_같은_분기_갱신이_된다(turso_like_db):
    ensure_schema(turso_like_db)
    _put(turso_like_db, classification="조용한 변화")
    _put(turso_like_db, classification="확인된 변화", financial=FIN_ON, news=NEWS_HIGH)
    got = get_classification(turso_like_db, "battery", "KR", 2026, 3)
    assert got["classification"] == "확인된 변화"
