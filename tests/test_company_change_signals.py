"""기업 카드 변화 신호 3개 + 변화 기업 판정 (docs/REDESIGN_SPEC.md 5-1, 5-2).

핵심은 원칙 4(계산 불가는 탈락이 아니다) - 이력이 모자라면 통과/실패가 아니라
데이터부족(None)이 나와야 한다. 그리고 매출 전환 경계는 곱셈 비교로만 판정한다 -
나눗셈 뒤 뺄셈은 부동소수점 오차로 정확히 1.20배인 경우를 놓칠 수 있다.
"""
from __future__ import annotations

import pytest

from src.analyzers.company_change_signals import (change_company, market_median_revenue_growth,
                                                   profit_transition, revenue_flow,
                                                   revenue_transition, revenue_yoy_growth)
from src.db.quarterly_financials import ensure_schema, insert_quarter, select_quarters


def _q(year, quarter, revenue=None, op=None, net=None):
    return {"fiscal_year": year, "fiscal_quarter": quarter, "revenue": revenue,
            "operating_income": op, "net_income": net, "source": "DART", "fs_div": "CFS",
            "derived": "reported", "collected_at": "2026-09-22T00:00:00"}


# ── 매출 전환 (5-1) ───────────────────────────────────────────

def test_1점2배_이상이면_통과한다():
    quarters = [_q(2026, 2, revenue=130), _q(2025, 2, revenue=100)]
    got = revenue_transition(quarters)
    assert got["pass"] is True and got["recent"] == 130 and got["year_ago"] == 100


def test_1점2배_미만이면_탈락한다():
    quarters = [_q(2026, 2, revenue=119), _q(2025, 2, revenue=100)]
    assert revenue_transition(quarters)["pass"] is False


def test_정확히_경계값이면_통과한다_부동소수점_오차_없이():
    """100 -> 120.0은 정확히 1.20배다. 나눗셈 방식(120.0/100 - 1)은 부동소수점 오차로
    0.19999999999999996이 나와 0.20 미만으로 오판한다 - 곱셈 비교라야 이 경계를 맞춘다."""
    naive_ratio = 120.0 / 100 - 1
    assert naive_ratio < 0.20, "이 테스트의 전제(나눗셈 방식의 함정) 자체가 재현되지 않는다"

    quarters = [_q(2026, 2, revenue=120.0), _q(2025, 2, revenue=100)]
    assert revenue_transition(quarters)["pass"] is True


def test_큰_금액에서도_경계값이_맞다():
    """8,500,000 -> 10,200,000도 정확히 1.20배다(더 실제 매출값에 가까운 크기)."""
    quarters = [_q(2026, 2, revenue=10_200_000.0), _q(2025, 2, revenue=8_500_000)]
    assert revenue_transition(quarters)["pass"] is True


def test_분기_재무가_아예_없으면_데이터부족이다():
    got = revenue_transition([])
    assert got["pass"] is None and got["reason"] is not None


def test_1년_전_분기_자체가_없으면_데이터부족이다():
    quarters = [_q(2026, 2, revenue=130)]
    got = revenue_transition(quarters)
    assert got["pass"] is None and "매출 없음" in got["reason"]


def test_1년_전_매출값이_비어있으면_데이터부족이다():
    quarters = [_q(2026, 2, revenue=130), _q(2025, 2, revenue=None)]
    assert revenue_transition(quarters)["pass"] is None


def test_최근_매출값이_비어있으면_데이터부족이다():
    quarters = [_q(2026, 2, revenue=None), _q(2025, 2, revenue=100)]
    assert revenue_transition(quarters)["pass"] is None


def test_1년_전_매출이_0이면_데이터부족이다():
    """0에 1.20을 곱해도 여전히 0이라 부등식이 항상 참이 되는 함정을 막는다."""
    quarters = [_q(2026, 2, revenue=1), _q(2025, 2, revenue=0)]
    got = revenue_transition(quarters)
    assert got["pass"] is None and "0 이하" in got["reason"]


def test_1년_전_매출이_음수면_데이터부족이다():
    """음수에 1.20을 곱하면 부등식 방향이 뒤집혀 의미가 없어진다."""
    quarters = [_q(2026, 2, revenue=1), _q(2025, 2, revenue=-100)]
    assert revenue_transition(quarters)["pass"] is None


def test_중간_분기가_비어있으면_1년_전을_건너뛰어_잇지_않는다():
    """raw 표에 네 분기가 있어도 정확히 4개 앞 분기가 없으면(2025Q3이 없음) 데이터부족이다 -
    2025Q1처럼 더 오래된 분기가 있어도 그걸로 대신하지 않는다."""
    quarters = [_q(2026, 2, revenue=130), _q(2026, 1, revenue=120),
                _q(2025, 4, revenue=110), _q(2025, 1, revenue=90)]
    got = revenue_transition(quarters)
    assert got["pass"] is None


def test_연도를_넘어가는_1년_전_비교도_맞다():
    quarters = [_q(2026, 1, revenue=130), _q(2025, 1, revenue=100)]
    assert revenue_transition(quarters)["pass"] is True


def test_기준배수를_설정으로_바꿀_수_있다():
    quarters = [_q(2026, 2, revenue=110), _q(2025, 2, revenue=100)]
    default_cfg = {"change_signal": {"revenue_transition_pct": 0.20, "revenue_flow_min_hits": 3}}
    loose_cfg = {"change_signal": {"revenue_transition_pct": 0.05, "revenue_flow_min_hits": 3}}
    assert revenue_transition(quarters, default_cfg)["pass"] is False
    assert revenue_transition(quarters, loose_cfg)["pass"] is True


# ── 매출 흐름 (5-1) ───────────────────────────────────────────

def _rising_5q(base=100, step=10):
    """5분기 연속 증가 - 4번 비교 모두 히트."""
    return [_q(2026, 2, revenue=base + step * 4), _q(2026, 1, revenue=base + step * 3),
            _q(2025, 4, revenue=base + step * 2), _q(2025, 3, revenue=base + step),
            _q(2025, 2, revenue=base)]


def test_4번_다_증가하면_통과한다():
    got = revenue_flow(_rising_5q())
    assert got["pass"] is True and got["hits"] == 4


def test_3번_증가하면_통과한다():
    """5-1: 4번 중 3번 이상. 130->140 증가, 135->130 감소, 110->135 증가, 100->110 증가 = 3번."""
    quarters = [_q(2026, 2, revenue=140), _q(2026, 1, revenue=130),
                _q(2025, 4, revenue=135), _q(2025, 3, revenue=110), _q(2025, 2, revenue=100)]
    got = revenue_flow(quarters)
    assert got["hits"] == 3 and got["pass"] is True


def test_2번만_증가하면_탈락한다():
    quarters = [_q(2026, 2, revenue=140), _q(2026, 1, revenue=130),
                _q(2025, 4, revenue=135), _q(2025, 3, revenue=145), _q(2025, 2, revenue=100)]
    # 130->140 증가, 135->130 감소, 145->135 감소, 100->145 증가 = 2번 증가
    got = revenue_flow(quarters)
    assert got["hits"] == 2 and got["pass"] is False


def test_같으면_증가가_아니다():
    """직전 분기와 매출이 같으면(증가가 아니다) 히트로 세지 않는다."""
    quarters = [_q(2026, 2, revenue=100), _q(2026, 1, revenue=100),
                _q(2025, 4, revenue=100), _q(2025, 3, revenue=100), _q(2025, 2, revenue=100)]
    got = revenue_flow(quarters)
    assert got["hits"] == 0 and got["pass"] is False


def test_5분기_중_하나라도_모자라면_데이터부족이다():
    quarters = _rising_5q()[:4]      # 2025Q2가 없다
    got = revenue_flow(quarters)
    assert got["pass"] is None and got["hits"] is None


def test_중간_분기가_비어도_데이터부족이다():
    """2025Q3이 빠지면 5개 목표 분기 중 하나를 못 채운다 - 있는 것만으로 계산하지 않는다."""
    quarters = [_q(2026, 2, revenue=140), _q(2026, 1, revenue=130),
                _q(2025, 4, revenue=120), _q(2025, 2, revenue=100)]   # 2025Q3 없음
    got = revenue_flow(quarters)
    assert got["pass"] is None


def test_매출_흐름_기준을_설정으로_바꿀_수_있다():
    quarters = [_q(2026, 2, revenue=140), _q(2026, 1, revenue=130),
                _q(2025, 4, revenue=135), _q(2025, 3, revenue=110), _q(2025, 2, revenue=100)]
    strict_cfg = {"change_signal": {"revenue_transition_pct": 0.20, "revenue_flow_min_hits": 4}}
    assert revenue_flow(quarters)["hits"] == 3
    assert revenue_flow(quarters)["pass"] is True               # 기본(3) 기준
    assert revenue_flow(quarters, strict_cfg)["pass"] is False  # 4로 올리면 탈락(히트 3)


# ── 이익 전환 (5-1) ───────────────────────────────────────────

def test_영업이익률이_개선되면_통과한다():
    quarters = [_q(2026, 2, revenue=100, op=15), _q(2025, 2, revenue=100, op=10)]
    got = profit_transition(quarters)
    assert got["pass"] is True


def test_영업이익률이_나빠지면_탈락한다():
    quarters = [_q(2026, 2, revenue=100, op=5), _q(2025, 2, revenue=100, op=10)]
    assert profit_transition(quarters)["pass"] is False


def test_적자에서_흑자로_전환하면_마진이_나빠도_통과한다():
    """1년 전 영업이익 < 0, 최근 > 0이면 마진 비교와 무관하게 통과."""
    quarters = [_q(2026, 2, revenue=1000, op=1), _q(2025, 2, revenue=100, op=-50)]
    got = profit_transition(quarters)
    assert got["pass"] is True


def test_흑자에서_적자로_가면_탈락한다():
    quarters = [_q(2026, 2, revenue=100, op=-10), _q(2025, 2, revenue=100, op=10)]
    assert profit_transition(quarters)["pass"] is False


def test_매출이나_영업이익이_없으면_데이터부족이다():
    assert profit_transition([_q(2026, 2, revenue=100, op=None), _q(2025, 2, revenue=100, op=10)])["pass"] is None
    assert profit_transition([_q(2026, 2, revenue=None, op=10), _q(2025, 2, revenue=100, op=10)])["pass"] is None


def test_1년_전_분기가_없으면_데이터부족이다():
    assert profit_transition([_q(2026, 2, revenue=100, op=10)])["pass"] is None


def test_매출이_0이어도_적자흑자_전환은_판정된다():
    """마진은 정의되지 않지만(0으로 나눔) 조건2(부호 전환)는 매출과 무관하다."""
    quarters = [_q(2026, 2, revenue=0, op=5), _q(2025, 2, revenue=0, op=-5)]
    got = profit_transition(quarters)
    assert got["pass"] is True and got["reason"] is None


def test_매출이_0이고_전환도_아니면_탈락이지_에러가_아니다():
    quarters = [_q(2026, 2, revenue=0, op=-1), _q(2025, 2, revenue=0, op=-5)]
    got = profit_transition(quarters)
    assert got["pass"] is False


# ── 변화 기업 판정 (5-2) ──────────────────────────────────────

def test_매출전환_통과_매출흐름_통과면_변화기업이다():
    quarters = _rising_5q()   # revenue_transition도 통과(100->140, 1.4배), flow도 통과
    got = change_company(quarters)
    assert got["changed"] is True


def test_매출전환_통과_이익전환만_통과해도_변화기업이다():
    # 매출 흐름은 탈락(계속 감소)하지만 이익 전환은 통과하는 조합.
    quarters = [_q(2026, 2, revenue=130, op=15), _q(2026, 1, revenue=135),
                _q(2025, 4, revenue=140), _q(2025, 3, revenue=145),
                _q(2025, 2, revenue=100, op=10)]
    rf = revenue_flow(quarters)
    assert rf["pass"] is False, "이 테스트는 매출 흐름이 탈락하는 조합이어야 한다"
    got = change_company(quarters)
    assert got["revenue_transition"]["pass"] is True
    assert got["profit_transition"]["pass"] is True
    assert got["changed"] is True


def test_매출전환_탈락하면_나머지와_무관하게_변화기업이_아니다():
    quarters = [_q(2026, 2, revenue=105, op=50), _q(2025, 2, revenue=100, op=-50)]
    rt = revenue_transition(quarters)
    assert rt["pass"] is False
    got = change_company(quarters)
    assert got["changed"] is False


def test_매출전환_통과해도_나머지_둘_다_탈락하면_변화기업이_아니다():
    quarters = [_q(2026, 2, revenue=130, op=5), _q(2026, 1, revenue=145),
                _q(2025, 4, revenue=150), _q(2025, 3, revenue=155),
                _q(2025, 2, revenue=100, op=20)]
    assert revenue_transition(quarters)["pass"] is True
    assert revenue_flow(quarters)["pass"] is False
    assert profit_transition(quarters)["pass"] is False
    assert change_company(quarters)["changed"] is False


def test_매출전환이_데이터부족이면_전체_판정도_데이터부족이다():
    got = change_company([_q(2026, 2, revenue=130)])   # 1년 전 분기가 없다
    assert got["changed"] is None
    assert got["revenue_flow"] is None and got["profit_transition"] is None


def test_매출전환_통과하고_나머지_둘_다_데이터부족이면_변화기업이_아니다():
    """5-2는 매출전환의 데이터부족만 전체에 전파한다고 했다 - 나머지 둘의 데이터부족은
    '통과 아님'으로 취급되어 changed=False가 나온다(None이 아니다)."""
    quarters = [_q(2026, 2, revenue=130), _q(2025, 2, revenue=100)]   # 2개 분기뿐, 흐름 계산 불가
    got = change_company(quarters)
    assert got["revenue_transition"]["pass"] is True
    assert got["revenue_flow"]["pass"] is None
    assert got["profit_transition"]["pass"] is None
    assert got["changed"] is False


# ── 화면 참고값: 유니버스 매출 증가율 중앙값 (5-1) ────────────

def test_매출_증가율을_비율로_돌려준다():
    quarters = [_q(2026, 2, revenue=120), _q(2025, 2, revenue=100)]
    assert revenue_yoy_growth(quarters) == pytest.approx(0.20)


def test_증가율_계산_불가면_None이다():
    assert revenue_yoy_growth([_q(2026, 2, revenue=120)]) is None
    assert revenue_yoy_growth([_q(2026, 2, revenue=120), _q(2025, 2, revenue=0)]) is None


def test_중앙값은_계산_가능한_값만으로_낸다():
    assert market_median_revenue_growth([0.1, 0.2, None, 0.3, None]) == pytest.approx(0.2)


def test_전부_None이면_중앙값도_None이다():
    assert market_median_revenue_growth([None, None]) is None


def test_빈_목록이면_중앙값도_None이다():
    assert market_median_revenue_growth([]) is None


# ── 운영 DB(Turso) 타입 + select_quarters 연동 ────────────────
#
# select_quarters()가 이미 타입을 보정하지만(연도·분기 int, 금액 float), 그 보정이
# 실제로 이 모듈의 계산까지 안전하게 이어지는지 end-to-end로 확인한다. 문자열이 그대로
# 새어나오면 `revenue >= year_ago * 1.2` 같은 비교가 조용히 틀린 답을 낸다.

def _put(conn, year, quarter, revenue, op, ticker="005930", market="KR", on="2026-09-20"):
    insert_quarter(conn, ticker, market, year, quarter,
                   {"revenue": revenue, "operating_income": op, "net_income": None, "fs_div": "CFS"},
                   "DART", "KRW", f"{on}T00:00:00")
    conn.commit()


def test_운영DB에서_select_quarters로_읽은_값으로_매출전환을_계산한다(turso_like_db):
    ensure_schema(turso_like_db)
    _put(turso_like_db, 2026, 2, 130, 20)
    _put(turso_like_db, 2025, 2, 100, 10)
    quarters = select_quarters(turso_like_db, "005930", "KR")
    got = revenue_transition(quarters)
    assert got["pass"] is True and isinstance(got["recent"], float)


def test_운영DB에서도_변화기업_판정이_된다(turso_like_db):
    ensure_schema(turso_like_db)
    _put(turso_like_db, 2026, 2, 140, 15)
    _put(turso_like_db, 2026, 1, 135, None)
    _put(turso_like_db, 2025, 4, 130, None)
    _put(turso_like_db, 2025, 3, 125, None)
    _put(turso_like_db, 2025, 2, 100, 10)
    quarters = select_quarters(turso_like_db, "005930", "KR")
    got = change_company(quarters)
    assert got["changed"] is True


def test_운영DB에서_연도_경계를_넘는_1년전_비교도_맞다(turso_like_db):
    """fiscal_year가 문자열로 오면 연도 산수(_shift_quarter)가 깨진다 - 2026Q1의 1년 전인
    2025Q1을 못 찾고 조용히 데이터부족이 되거나 엉뚱한 분기를 짚을 수 있다."""
    ensure_schema(turso_like_db)
    _put(turso_like_db, 2026, 1, 130, 10)
    _put(turso_like_db, 2025, 1, 100, 5)
    quarters = select_quarters(turso_like_db, "005930", "KR")
    got = revenue_transition(quarters)
    assert got["pass"] is True and got["year_ago"] == 100
