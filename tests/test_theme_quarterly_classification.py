"""테마 4칸 분류 (docs/REDESIGN_SPEC.md 7장).

재무 신호 "켜짐"(7-1)의 비율(30%)과 최소 개수(2곳)는 AND 조건이다 - 하나만 보면
소속 기업이 적은 테마가 쉽게 통과하거나(비율만) 큰 테마가 절대 안 켜지는(개수만)
문제가 생긴다. 분류(7-3)는 재무·뉴스 둘 다 판정이 나와야 하고, 하나라도 데이터부족이면
분류하지 않는다.
"""
from __future__ import annotations

import pytest

from src.analyzers.theme_quarterly_classification import (CONFIRMED_CHANGE, LEADING_HYPE,
                                                           OFF_RADAR, QUIET_CHANGE, classify,
                                                           financial_signal)

DEFAULT_CFG = {"financial_on": {"change_ratio": 0.30, "min_changed": 2, "min_judged": 2}}


# ── 재무 신호 "켜짐" (7-1) ─────────────────────────────────────

def test_비율과_개수_둘_다_넘으면_켜짐이다():
    flags = [True, True, True, False, False, False, False]   # 3/7 = 42.9%, 3곳
    got = financial_signal(flags, DEFAULT_CFG)
    assert got["on"] is True and got["changed"] == 3 and got["judged"] == 7


def test_비율은_넘어도_개수가_모자라면_꺼짐이다():
    """기업 3곳짜리 테마에서 1곳만 변해도 비율은 33%라 30%를 넘지만, 개수 2곳 미만이라 꺼짐."""
    flags = [True, False, False]
    got = financial_signal(flags, DEFAULT_CFG)
    assert got["ratio"] == pytest.approx(1 / 3) and got["ratio"] >= 0.30
    assert got["on"] is False


def test_개수는_넘어도_비율이_모자라면_꺼짐이다():
    """10곳 중 2곳(20%)은 개수 조건은 넘지만 비율 30%에 못 미친다."""
    flags = [True, True] + [False] * 8
    got = financial_signal(flags, DEFAULT_CFG)
    assert got["ratio"] == pytest.approx(0.20)
    assert got["on"] is False


def test_정확히_경계값이면_켜짐이다():
    """10곳 중 3곳 = 정확히 30%."""
    flags = [True, True, True] + [False] * 7
    got = financial_signal(flags, DEFAULT_CFG)
    assert got["ratio"] == pytest.approx(0.30) and got["on"] is True


def test_판정_가능_기업이_2곳_미만이면_데이터부족이다():
    got = financial_signal([True], DEFAULT_CFG)
    assert got["on"] is None and "2곳" in got["reason"]


def test_전부_데이터부족이면_전체도_데이터부족이다():
    got = financial_signal([None, None, None], DEFAULT_CFG)
    assert got["on"] is None and got["judged"] == 0


def test_빈_목록도_데이터부족이다():
    got = financial_signal([], DEFAULT_CFG)
    assert got["on"] is None


def test_데이터부족_기업은_분모에서_뺀다():
    """10곳 중 8곳이 데이터부족이어도, 판정된 2곳이 둘 다 변화 기업이면 100%로 켜진다 -
    판정 못 낸 기업을 분모에 넣으면 '10곳 중 2곳(20%)'이 되어 꺼짐으로 잘못 나온다."""
    flags = [True, True] + [None] * 8
    got = financial_signal(flags, DEFAULT_CFG)
    assert got["judged"] == 2 and got["ratio"] == pytest.approx(1.0) and got["on"] is True


def test_기준값을_설정으로_바꿀_수_있다():
    flags = [True, True] + [False] * 8   # 20%
    loose_cfg = {"financial_on": {"change_ratio": 0.10, "min_changed": 1, "min_judged": 2}}
    assert financial_signal(flags, DEFAULT_CFG)["on"] is False
    assert financial_signal(flags, loose_cfg)["on"] is True


def test_설정을_안_주면_기본값을_쓴다():
    """config=None이면 quarterly_thresholds.load()의 기본값을 그대로 쓴다."""
    flags = [True, True, True] + [False] * 7
    got = financial_signal(flags)
    assert got["on"] is True


# ── 4칸 분류 (7-3) ────────────────────────────────────────────

def test_켜짐_적음은_조용한_변화다():
    assert classify(True, False) == QUIET_CHANGE


def test_켜짐_많음은_확인된_변화다():
    assert classify(True, True) == CONFIRMED_CHANGE


def test_꺼짐_많음은_기대_선행이다():
    assert classify(False, True) == LEADING_HYPE


def test_꺼짐_적음은_관심_밖이다():
    assert classify(False, False) == OFF_RADAR


def test_재무가_데이터부족이면_분류하지_않는다():
    assert classify(None, True) is None
    assert classify(None, False) is None


def test_뉴스가_데이터부족이면_분류하지_않는다():
    assert classify(True, None) is None
    assert classify(False, None) is None


def test_둘_다_데이터부족이면_분류하지_않는다():
    assert classify(None, None) is None
