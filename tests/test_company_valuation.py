"""기업 카드 밸류 위치 (docs/REDESIGN_SPEC.md 4-3, 5-4).

핵심은 두 가지다. (1) "최근 4분기"는 raw 표에 있는 아무 4개가 아니라 정확히 연속된
4개 분기여야 한다(중간에 하나라도 비면 데이터부족). (2) 테마 3등분은 개별 기업이
아니라 테마 전체 단위로 데이터부족을 판정한다(3곳 미만이면 전원 None).
"""
from __future__ import annotations

import pytest

from src.analyzers.company_valuation import CHEAP, EXPENSIVE, MID, per, psr, theme_valuation_tiers


def _q(year, quarter, revenue=None, net=None):
    return {"fiscal_year": year, "fiscal_quarter": quarter, "revenue": revenue,
            "operating_income": None, "net_income": net, "source": "DART", "fs_div": "CFS",
            "derived": "reported", "collected_at": "2026-09-22T00:00:00"}


def _4q(revenues=(100, 100, 100, 100), nets=(10, 10, 10, 10)):
    """2026Q2부터 거꾸로 4개 연속 분기."""
    quarters = [(2026, 2), (2026, 1), (2025, 4), (2025, 3)]
    return [_q(y, q, revenue=r, net=n) for (y, q), r, n in zip(quarters, revenues, nets)]


# ── PSR ───────────────────────────────────────────────────────

def test_시가총액_나누기_4분기_매출합이다():
    quarters = _4q(revenues=(100, 100, 100, 100))
    assert psr(2000, quarters) == pytest.approx(5.0)   # 2000 / 400


def test_시가총액이_없으면_None이다():
    assert psr(None, _4q()) is None


def test_4분기_중_하나라도_매출이_없으면_None이다():
    quarters = _4q()
    quarters[2]["revenue"] = None
    assert psr(2000, quarters) is None


def test_4분기가_다_채워지지_않으면_None이다():
    """3개만 있고 하나가 raw 표에 아예 없는 경우."""
    quarters = _4q()[:3]
    assert psr(2000, quarters) is None


def test_중간_분기가_비면_있는_것만으로_합치지_않는다():
    """2025Q4가 빠지면(2026Q2·Q1, 2025Q3만 있음) 연속 4분기가 아니므로 None -
    2025Q2까지 끌어와 대신 채우지 않는다."""
    quarters = [_q(2026, 2, revenue=100), _q(2026, 1, revenue=100),
                _q(2025, 3, revenue=100), _q(2025, 2, revenue=100)]
    assert psr(2000, quarters) is None


def test_매출합이_0이하면_None이다():
    quarters = _4q(revenues=(100, 100, -150, -150))   # 합계 -100
    assert psr(2000, quarters) is None


def test_매출합이_정확히_0이면_None이다():
    quarters = _4q(revenues=(100, 100, -100, -100))
    assert psr(2000, quarters) is None


def test_분기_재무가_아예_없으면_None이다():
    assert psr(2000, []) is None


# ── PER ───────────────────────────────────────────────────────

def test_시가총액_나누기_4분기_순이익합이다():
    quarters = _4q(nets=(10, 10, 10, 10))
    assert per(2000, quarters) == pytest.approx(50.0)   # 2000 / 40


def test_순이익합이_0이하면_표시_안_한다():
    """SPEC 5-4: 흑자 기업만 PER을 보여준다."""
    quarters = _4q(nets=(10, 10, -30, -30))   # 합계 -40
    assert per(2000, quarters) is None


def test_순이익합이_정확히_0이면_표시_안_한다():
    quarters = _4q(nets=(10, 10, -10, -10))
    assert per(2000, quarters) is None


def test_4분기_중_하나라도_순이익이_없으면_None이다():
    quarters = _4q()
    quarters[1]["net_income"] = None
    assert per(2000, quarters) is None


def test_매출과_순이익_결측은_따로_본다():
    """매출은 다 있어도 순이익 하나가 없으면 PSR은 되고 PER만 None이다."""
    quarters = _4q(revenues=(100, 100, 100, 100))
    quarters[0]["net_income"] = None
    assert psr(2000, quarters) == pytest.approx(5.0)
    assert per(2000, quarters) is None


# ── 테마 3등분 ────────────────────────────────────────────────

def test_9곳을_3등분한다():
    psr_map = {f"t{i}": float(i) for i in range(1, 10)}   # 1..9, 낮을수록 쌈
    got = theme_valuation_tiers(psr_map)
    cheap = [t for t, v in got.items() if v == CHEAP]
    mid = [t for t, v in got.items() if v == MID]
    expensive = [t for t, v in got.items() if v == EXPENSIVE]
    assert set(cheap) == {"t1", "t2", "t3"}
    assert set(mid) == {"t4", "t5", "t6"}
    assert set(expensive) == {"t7", "t8", "t9"}


def test_3의_배수가_아니어도_최대한_고르게_나눈다():
    """4곳: 순위 기반이라 애매하게 안 갈린다(1/1/2)."""
    psr_map = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
    got = theme_valuation_tiers(psr_map)
    assert got["a"] == CHEAP
    assert got["b"] == MID
    assert got["d"] == EXPENSIVE


def test_판정_가능_기업이_3곳_미만이면_테마_전체가_데이터부족이다():
    psr_map = {"a": 1.0, "b": 2.0, "c": None}
    got = theme_valuation_tiers(psr_map)
    assert got == {"a": None, "b": None, "c": None}


def test_정확히_3곳이면_등분한다():
    psr_map = {"a": 1.0, "b": 2.0, "c": 3.0}
    got = theme_valuation_tiers(psr_map)
    assert got == {"a": CHEAP, "b": MID, "c": EXPENSIVE}


def test_None인_기업은_등급이_없어도_분모에서_빠진다():
    """8곳 중 2곳이 PSR 계산 불가여도, 나머지 6곳으로는 3등분이 정상 진행된다."""
    psr_map = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0, "f": 6.0,
              "none1": None, "none2": None}
    got = theme_valuation_tiers(psr_map)
    assert got["none1"] is None and got["none2"] is None
    assert got["a"] == CHEAP and got["f"] == EXPENSIVE


def test_빈_테마도_데이터부족이다():
    assert theme_valuation_tiers({}) == {}


def test_전부_같은_PSR이어도_순서대로_나뉜다():
    """값이 동률이어도 죽지 않고 안정적으로 등분된다."""
    psr_map = {f"t{i}": 5.0 for i in range(6)}
    got = theme_valuation_tiers(psr_map)
    assert sorted(got.values()) == sorted([CHEAP, CHEAP, MID, MID, EXPENSIVE, EXPENSIVE])


# ── 운영 DB(Turso) 타입 + select_quarters 연동 ────────────────
#
# select_quarters()가 타입을 보정하지만, 그 보정이 실제로 이 모듈의 계산까지
# 안전하게 이어지는지 end-to-end로 확인한다.

from src.db.quarterly_financials import ensure_schema, insert_quarter, select_quarters  # noqa: E402


def _put(conn, year, quarter, revenue, net, ticker="005930", market="KR", on="2026-09-20"):
    insert_quarter(conn, ticker, market, year, quarter,
                   {"revenue": revenue, "operating_income": None, "net_income": net, "fs_div": "CFS"},
                   "DART", "KRW", f"{on}T00:00:00")
    conn.commit()


def test_운영DB에서_select_quarters로_읽은_값으로_PSR을_계산한다(turso_like_db):
    ensure_schema(turso_like_db)
    for y, q in [(2026, 2), (2026, 1), (2025, 4), (2025, 3)]:
        _put(turso_like_db, y, q, revenue=100, net=10)
    quarters = select_quarters(turso_like_db, "005930", "KR")
    assert psr(2000, quarters) == pytest.approx(5.0)
    assert per(2000, quarters) == pytest.approx(50.0)


def test_운영DB에서_연도_경계를_넘는_4분기_합산도_맞다(turso_like_db):
    """fiscal_year가 문자열로 오면 분기 산수가 깨진다 - 2026Q1 기준 4분기 전은 2025Q2다."""
    ensure_schema(turso_like_db)
    for y, q in [(2026, 1), (2025, 4), (2025, 3), (2025, 2)]:
        _put(turso_like_db, y, q, revenue=100, net=10)
    quarters = select_quarters(turso_like_db, "005930", "KR")
    assert psr(2000, quarters) == pytest.approx(5.0)
