"""분기 뉴스 집계 (docs/REDESIGN_SPEC.md 6-3, 7-2).

뉴스 비율 = 이번 분기 기사 수 ÷ 직전 4분기 평균 기사 수.
핵심은 "계산 불가를 탈락으로 처리하지 않는다"(원칙 4) - 이력이 모자라면 비율이 아니라
데이터부족이 나와야 한다. 조용히 작은 값이 나오면 그 테마는 영영 "관심 밖"에 머문다.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.analyzers.theme_news_quarterly import (aggregate_quarters, news_ratio, prior_quarters,
                                                quarter_mondays, quarter_of)
from src.db.theme_signals import ensure_schema, get_weekly_news_counts, upsert_news_weekly


# ── 분기 나누기 ───────────────────────────────────────────────

def test_주의_월요일이_속한_분기로_센다():
    assert quarter_of(date(2026, 7, 6)) == (2026, 3)
    assert quarter_of(date(2026, 3, 30)) == (2026, 1)


def test_분기_경계에_걸친_주는_월요일_쪽으로_간다():
    """2026-06-29(월)은 6월이라 2분기다. 그 주의 금요일은 7월이지만 나누지 않는다."""
    assert quarter_of(date(2026, 6, 29)) == (2026, 2)


def test_분기의_월요일_수를_센다():
    assert quarter_mondays(2026, 3)[0] == date(2026, 7, 6)
    assert quarter_mondays(2026, 3)[-1] == date(2026, 9, 28)
    assert len(quarter_mondays(2026, 3)) == 13


def test_4분기의_다음_분기는_다음_해_1분기다():
    assert quarter_mondays(2026, 4)[-1] == date(2026, 12, 28)


def test_직전_4분기를_최근순으로_돌려준다():
    assert prior_quarters(2026, 3) == [(2026, 2), (2026, 1), (2025, 4), (2025, 3)]


def test_해를_넘어가도_직전_분기가_맞다():
    assert prior_quarters(2026, 1) == [(2025, 4), (2025, 3), (2025, 2), (2025, 1)]


# ── 분기 합계 ─────────────────────────────────────────────────

def _full_quarter(year, quarter, per_week):
    return {w.isoformat(): per_week for w in quarter_mondays(year, quarter)}


def test_주간_건수를_분기로_합친다():
    weekly = _full_quarter(2026, 3, 10)
    got = aggregate_quarters(weekly)[(2026, 3)]
    assert got["articles"] == 130 and got["weeks"] == 13 and got["complete"] is True


def test_주가_조금_빠져도_분기를_쓴다():
    """13주 중 11주면 쓴다 - 한두 주 결측으로 분기를 통째로 버리지 않는다."""
    weekly = _full_quarter(2026, 3, 10)
    for w in list(weekly)[:2]:
        del weekly[w]
    assert aggregate_quarters(weekly)[(2026, 3)]["complete"] is True


def test_주가_많이_빠지면_그_분기는_쓰지_않는다():
    """합으로 비교하므로, 주가 빠진 분기를 그대로 쓰면 조용히 작게 나온다."""
    weekly = _full_quarter(2026, 3, 10)
    for w in list(weekly)[:5]:
        del weekly[w]
    assert aggregate_quarters(weekly)[(2026, 3)]["complete"] is False


def test_건수가_없는_주는_세지_않는다():
    weekly = _full_quarter(2026, 3, 10)
    weekly[date(2026, 7, 6).isoformat()] = None
    got = aggregate_quarters(weekly)[(2026, 3)]
    assert got["weeks"] == 12 and got["articles"] == 120


# ── 뉴스 비율 ─────────────────────────────────────────────────

def _five_quarters(this_per_week, prior_per_week):
    weekly = _full_quarter(2026, 3, this_per_week)
    for y, q in prior_quarters(2026, 3):
        weekly |= _full_quarter(y, q, prior_per_week)
    return aggregate_quarters(weekly)


def test_직전_4분기_평균과_비교한다():
    """직전 4분기가 주당 10건씩, 이번 분기가 주당 20건이면 약 2배."""
    got = news_ratio(_five_quarters(20, 10), (2026, 3))
    assert got["reason"] is None
    assert got["ratio"] == pytest.approx(2.0, abs=0.1)


def test_뉴스_많음_기준_1점5배를_넘는지_본다():
    assert news_ratio(_five_quarters(16, 10), (2026, 3))["ratio"] >= 1.5
    assert news_ratio(_five_quarters(14, 10), (2026, 3))["ratio"] < 1.5


def test_직전_분기가_하나라도_없으면_데이터부족이다():
    """SPEC 6-3: 있는 분기만으로 평균 내지 않는다."""
    quarters = _five_quarters(20, 10)
    del quarters[(2025, 3)]
    got = news_ratio(quarters, (2026, 3))
    assert got["ratio"] is None and "2025Q3" in got["reason"]


def test_직전_분기가_주_부족이면_데이터부족이다():
    quarters = _five_quarters(20, 10)
    quarters[(2025, 4)]["complete"] = False
    got = news_ratio(quarters, (2026, 3))
    assert got["ratio"] is None and "2025Q4" in got["reason"]


def test_분기_초에_돌리면_데이터부족이다():
    """2026Q3 13주 중 4주만 모인 상태 - 아직 그 분기를 대표하지 못한다."""
    weekly = {w.isoformat(): 20 for w in quarter_mondays(2026, 3)[:4]}
    for y, q in prior_quarters(2026, 3):
        weekly |= _full_quarter(y, q, 10)
    got = news_ratio(aggregate_quarters(weekly), (2026, 3))
    assert got["ratio"] is None and "이번 분기" in got["reason"] and "4/13주" in got["reason"]


def test_분기_후반이면_그때까지의_주당_평균으로_낸다():
    """13주 중 11주면 낸다. 주당 평균이라 남은 2주가 없어도 값이 기울지 않는다."""
    weekly = {w.isoformat(): 20 for w in quarter_mondays(2026, 3)[:11]}
    for y, q in prior_quarters(2026, 3):
        weekly |= _full_quarter(y, q, 10)
    got = news_ratio(aggregate_quarters(weekly), (2026, 3))
    assert got["reason"] is None and got["ratio"] == pytest.approx(2.0, abs=0.01)


def test_직전_기사_수가_0이면_데이터부족이다():
    """0으로 나누지 않는다."""
    got = news_ratio(_five_quarters(20, 0), (2026, 3))
    assert got["ratio"] is None and got["reason"] is not None


def test_데이터부족이어도_이번_분기_건수는_돌려준다():
    """화면에 '몇 건인지'는 보여줄 수 있어야 한다."""
    quarters = _five_quarters(20, 10)
    del quarters[(2025, 3)]
    assert news_ratio(quarters, (2026, 3))["this_quarter"] == 260


# ── 두 표 합쳐 읽기 ───────────────────────────────────────────

def _signal_week(conn, theme_id, market, week_start, count):
    conn.execute(
        "INSERT INTO theme_signals (theme_id, market, week_start, news_count, computed_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (theme_id, market, week_start, count, "2026-09-21T00:00:00"))
    conn.commit()


def _weekly_row(conn, theme_id, market, week_start, count):
    upsert_news_weekly(conn, theme_id, market, week_start, count, count, 0, 0, 0, "2026-09-21T00:00:00")
    conn.commit()


def test_백필_표와_주간_표를_이어_읽는다(memory_db):
    """백필은 2026-07-06까지, 주간 수집은 2026-07-13부터 - 둘을 합쳐야 분기가 채워진다."""
    ensure_schema(memory_db)
    _weekly_row(memory_db, "ai_semiconductor", "US", "2026-07-06", 100)
    _signal_week(memory_db, "ai_semiconductor", "US", "2026-07-13", 120)
    got = get_weekly_news_counts(memory_db, "ai_semiconductor", "US")
    assert got == {"2026-07-06": 100, "2026-07-13": 120}


def test_같은_주가_양쪽에_있으면_백필_표를_쓴다(memory_db):
    ensure_schema(memory_db)
    _signal_week(memory_db, "ai_semiconductor", "US", "2026-07-06", 111)
    _weekly_row(memory_db, "ai_semiconductor", "US", "2026-07-06", 100)
    assert get_weekly_news_counts(memory_db, "ai_semiconductor", "US") == {"2026-07-06": 100}


def test_다른_테마_시장은_섞이지_않는다(memory_db):
    ensure_schema(memory_db)
    _weekly_row(memory_db, "ai_semiconductor", "US", "2026-07-06", 100)
    _weekly_row(memory_db, "battery", "KR", "2026-07-06", 50)
    assert get_weekly_news_counts(memory_db, "battery", "KR") == {"2026-07-06": 50}


def test_키워드가_바뀐_주_이전은_빼고_읽는다(memory_db):
    """themes.yaml 유지보수 규칙 2 - 바뀌기 전 건수와 추이를 잇지 않는다."""
    ensure_schema(memory_db)
    _weekly_row(memory_db, "machinery", "KR", "2026-09-07", 40)
    _weekly_row(memory_db, "machinery", "KR", "2026-09-21", 90)
    got = get_weekly_news_counts(memory_db, "machinery", "KR", since="2026-09-14")
    assert got == {"2026-09-21": 90}


def test_운영DB에서도_건수가_숫자다(turso_like_db):
    """Turso는 정수를 문자열로 돌려준다 - 그대로 합치면 분기 합계가 글자 이어붙이기가 된다."""
    ensure_schema(turso_like_db)
    _weekly_row(turso_like_db, "ai_semiconductor", "US", "2026-07-06", 100)
    _signal_week(turso_like_db, "ai_semiconductor", "US", "2026-07-13", 120)
    got = get_weekly_news_counts(turso_like_db, "ai_semiconductor", "US")
    assert got == {"2026-07-06": 100, "2026-07-13": 120}
    assert all(isinstance(v, int) for v in got.values())


# ── 보고 스크립트 (scripts/report_quarterly_news.py) ──────────

from scripts.report_quarterly_news import parse_quarter, previous_quarter, week_monday  # noqa: E402


def test_분기_문자열을_읽는다():
    assert parse_quarter("2026Q3") == (2026, 3)
    assert parse_quarter("2026q1") == (2026, 1)


def test_직전_분기를_기본값으로_쓴다():
    """분기 첫날(10/1)에 돌리면 막 끝난 분기(Q3)를 본다 - 진행 중인 Q4가 아니다."""
    assert previous_quarter(date(2026, 10, 1)) == (2026, 3)
    assert previous_quarter(date(2026, 1, 1)) == (2025, 4)


def test_그_날이_속한_주의_월요일을_찾는다():
    assert week_monday(date(2026, 9, 17)) == date(2026, 9, 14)   # 목요일 -> 그 주 월요일
    assert week_monday(date(2026, 9, 14)) == date(2026, 9, 14)
