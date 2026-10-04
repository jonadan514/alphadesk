"""뉴스 수집원이 바뀐 시장은 바뀌기 전 이력을 기준선에 잇지 않는다.

2026-10-01: KR 수집원이 구글 RSS에서 네이버 뉴스 API로 바뀌었다. 같은 주제의 건수가
2-3배 달라서(AI 반도체 334 -> 721) 이어 붙이면 34개 테마 중 33개가 가짜 "급증"이 됐다.
DB는 로컬 sqlite 메모리를 쓴다 - 네트워크·운영 DB를 타지 않는다.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from src.db.theme_signals import (ensure_schema, get_prior_news_counts, news_history_since,
                                  upsert_news_signal)


def test_KR은_수집원_전환_주부터():
    assert news_history_since({}, "KR") == "2026-09-28"


def test_US도_수집원_전환_주부터():
    """2026-10-04 미국도 구글 -> Finnhub 소속 기업 뉴스로 바뀌었다(정의 자체가 다름)."""
    assert news_history_since({}, "US") == "2026-09-28"


def test_키워드_변경이_더_늦으면_그쪽을_따른다():
    theme = {"keywords_changed_at": date(2026, 10, 14)}  # 수요일
    assert news_history_since(theme, "KR") == "2026-10-12"  # 그 주 월요일


def test_키워드_변경이_더_이르면_수집원_전환이_이긴다():
    theme = {"keywords_changed_at": date(2026, 9, 15)}
    assert news_history_since(theme, "KR") == "2026-09-28"


def test_US도_더_늦은_쪽을_따른다():
    theme = {"keywords_changed_at": date(2026, 9, 15)}
    assert news_history_since(theme, "US") == "2026-09-28"


def _seed(conn, market, weeks_counts):
    for wk, n in weeks_counts:
        upsert_news_signal(conn, "ai_semiconductor", market, wk, n, None, None, "na", False, "t")


def test_KR_기준선에_구글_시절_주는_들어가지_않는다():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    # 구글 시절 3주 + 네이버 첫 주(9/28)
    _seed(conn, "KR", [("2026-09-07", 300), ("2026-09-14", 310), ("2026-09-21", 330), ("2026-09-28", 721)])
    since = news_history_since({}, "KR")
    # 다음 주(10/5) 기준선: 네이버 이력은 9/28 한 주뿐 - 구글 주가 섞이면 안 된다
    assert get_prior_news_counts(conn, "ai_semiconductor", "KR", "2026-10-05", weeks=8, since=since) == [721]
    # since를 안 주면 옛 동작 - 이게 가짜 급증의 원인이었다
    assert len(get_prior_news_counts(conn, "ai_semiconductor", "KR", "2026-10-05", weeks=8)) == 4
