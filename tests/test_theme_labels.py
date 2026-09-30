"""6개 조합 라벨 (docs/TEST_PLAN.md 5장, SPEC_phase_a_signals.md 5장).

이 6개만 라벨을 단다. 축이 하나라도 na/None이면 라벨이 없고, 표에 없는 조합도 없다.
"모든 조합에 이름을 붙이면 오히려 정보가 사라진다"는 설계 원칙이다.
"""
from __future__ import annotations

import itertools

import pytest

from analyzers.theme_labels import compute_label

UP = ("up1", "up2")

# 규칙 형태(뉴스 집합, 실적 집합, 주가 집합, 라벨) - SPEC 표를 그대로 옮긴 것.
# 라벨은 축 값의 "묶음"에 붙는다(예: Full Alignment는 세 축이 각각 up1/up2 어느 쪽이든).
SPEC_RULES = [
    ({"up2"}, {"flat"}, set(UP), "Early Buzz"),
    (set(UP), set(UP), set(UP), "Full Alignment"),
    ({"flat", "down"}, {"up2"}, {"flat"}, "Quiet Strength"),
    ({"up2"}, {"down"}, {"up2"}, "Overheated Buzz"),
    ({"down"}, {"down"}, {"down"}, "Full Decline"),
    ({"down"}, set(UP), {"down"}, "Quiet Recovery"),
]
ALL_ARROWS = ["up2", "up1", "flat", "down"]


def expected_label(news, earn, price):
    for n, e, p, label in SPEC_RULES:
        if news in n and earn in e and price in p:
            return label
    return None


# 대표 조합(사람이 읽기 쉽게 명시한 것)
SPEC_TABLE = [
    ("up2", "flat", "up1", "Early Buzz"),
    ("up2", "flat", "up2", "Early Buzz"),
    ("up1", "up1", "up1", "Full Alignment"),
    ("up2", "up2", "up2", "Full Alignment"),
    ("up1", "up2", "up1", "Full Alignment"),
    ("up2", "up2", "up1", "Full Alignment"),
    ("flat", "up2", "flat", "Quiet Strength"),
    ("down", "up2", "flat", "Quiet Strength"),
    ("up2", "down", "up2", "Overheated Buzz"),
    ("down", "down", "down", "Full Decline"),
    ("down", "up1", "down", "Quiet Recovery"),
    ("down", "up2", "down", "Quiet Recovery"),
]


@pytest.mark.parametrize("news,earn,price,label", SPEC_TABLE)
def test_SPEC_표의_조합에는_라벨을_붙인다(news, earn, price, label):
    assert compute_label(news, earn, price) == label


@pytest.mark.parametrize("missing", ["na", None])
@pytest.mark.parametrize("which", [0, 1, 2])
def test_축이_하나라도_비어_있으면_라벨이_없다(which, missing):
    arrows = ["up2", "up2", "up2"]        # 비어 있지만 않으면 Full Alignment가 되는 조합
    arrows[which] = missing
    assert compute_label(*arrows) is None


def test_표에_없는_조합은_라벨이_없다():
    assert compute_label("flat", "flat", "flat") is None
    assert compute_label("up1", "down", "up1") is None       # Overheated는 뉴스·주가가 up2여야 한다
    assert compute_label("up1", "flat", "up1") is None       # Early Buzz는 뉴스가 up2여야 한다


def test_64개_조합_전부가_SPEC_규칙과_같은_결과를_낸다():
    """표에 없는 조합에 라벨이 새어 나오거나, 표에 있는 조합에서 빠지지 않는지 전수 확인한다."""
    for n, e, p in itertools.product(ALL_ARROWS, repeat=3):
        assert compute_label(n, e, p) == expected_label(n, e, p), f"조합 {(n, e, p)}"


def test_라벨은_6종류뿐이다():
    labels = {compute_label(n, e, p)
              for n, e, p in itertools.product(["up2", "up1", "flat", "down"], repeat=3)}
    labels.discard(None)
    assert labels == {"Early Buzz", "Full Alignment", "Quiet Strength",
                      "Overheated Buzz", "Full Decline", "Quiet Recovery"}
