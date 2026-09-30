"""뉴스 수집 실패와 '뉴스 가뭄'을 구분한다 (scripts/collect_theme_news.py).

2026-09-28에 구글 뉴스가 Actions IP를 막아 전 테마가 0건이 됐는데, 그 0이
그대로 theme_signals에 저장됐다. 기준선(get_prior_news_counts)은 news_count가
NULL인 주만 제외하므로 0은 그대로 섞여 들어간다 - 0이 쌓이면 중앙값이 0이 되고
뉴스 축이 영구히 죽는다.

테마 하나가 0건인 건 실제 정보다. 전 테마가 동시에 0건인 건 소스가 막힌 것이다.
이 구분이 되는지만 검증한다(네트워크는 타지 않는다).
"""
from __future__ import annotations

import statistics

from scripts.collect_theme_news import BASELINE_MIN_WEEKS, compute_news_arrow, is_collection_failure


# ── 수집 실패 판정 ─────────────────────────────────────────────

def test_전_테마가_0건이면_수집_실패다():
    assert is_collection_failure([0, 0, 0, 0, 0]) is True


def test_한_테마만_0건이면_실패가_아니다():
    """그 테마에 그 주 뉴스가 없었던 것 - 실제 정보라 0으로 저장해야 한다."""
    assert is_collection_failure([120, 0, 88, 40]) is False


def test_전부_0이어도_대상이_없으면_실패로_치지_않는다():
    """수집 대상이 0개면 판단할 근거 자체가 없다."""
    assert is_collection_failure([]) is False


# ── 기준선 오염이 실제로 일어나는지(회귀 방지) ────────────────

def test_0이_섞이면_기준선_중앙값이_무너진다():
    """왜 NULL로 저장해야 하는지를 숫자로 고정해 둔다.

    기준선은 직전 8주 중앙값이다. 0이 4주까지는 중앙값이 버티지만 5주가 되면
    0으로 내려앉고, 그 시점부터 compute_news_arrow가 ratio를 못 낸다.
    """
    healthy = [300] * 8
    assert statistics.median(healthy) == 300

    # 0이 4개 섞여도 중앙값은 아직 살아 있다
    assert statistics.median([0, 0, 0, 0, 300, 300, 300, 300]) == 150
    # 5개부터 무너진다
    assert statistics.median([0, 0, 0, 0, 0, 300, 300, 300]) == 0


def test_기준선이_0이면_비율을_내지_않는다():
    baseline, ratio, arrow = compute_news_arrow(
        news_count=250, min_articles=10, prior_counts=[0] * 8,
        thresholds={"strong_up": 2.0, "up": 1.3, "down": 0.7})
    assert baseline == 0
    assert ratio is None
    assert arrow == "na"


def test_직전_주가_모자라면_판정_보류():
    baseline, ratio, arrow = compute_news_arrow(
        news_count=250, min_articles=10,
        prior_counts=[300] * (BASELINE_MIN_WEEKS - 1),
        thresholds={"strong_up": 2.0, "up": 1.3, "down": 0.7})
    assert (baseline, ratio, arrow) == (None, None, "na")


def test_정상일_때는_비율과_화살표가_나온다():
    thresholds = {"strong_up": 2.0, "up": 1.3, "down": 0.7}
    # 중앙값 100, 이번 주 250 -> 2.5배 -> up2
    _, ratio, arrow = compute_news_arrow(250, 10, [100] * 8, thresholds)
    assert ratio == 2.5 and arrow == "up2"
    # 중앙값 100, 이번 주 50 -> 0.5배 -> down
    _, ratio, arrow = compute_news_arrow(50, 10, [100] * 8, thresholds)
    assert ratio == 0.5 and arrow == "down"
