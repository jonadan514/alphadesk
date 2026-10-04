"""네이버 뉴스 검색 경로 (src/collectors/theme_news_collector.py).

구글 뉴스 RSS가 Actions IP에서 막힌 뒤 추가한 한국 대체 소스다. 네트워크를 타지
않고, requests.get을 가짜로 바꿔 파싱·필터링 규칙만 검증한다.

핵심은 두 가지다.
  - 네이버는 날짜 범위 검색이 없다. 최신순으로 받아와 호출부가 직접 창을 자른다.
  - 조회 실패를 0건으로 둔갑시키지 않는다(구글 경로와 같은 규칙).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

import src.collectors.theme_news_collector as tnc


def _item(title: str, url: str, pub: str) -> dict:
    return {"title": title, "originallink": url, "link": url, "pubDate": pub}


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture
def naver_env(monkeypatch):
    monkeypatch.setenv("NAVER_CLIENT_ID", "test-id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-secret")


def test_키가_없으면_예외를_올린다(monkeypatch):
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="NAVER_CLIENT"):
        tnc.search_naver_news_kr("조선업", date(2026, 9, 21), date(2026, 9, 28))


def test_창_밖_기사를_걸러낸다(naver_env, monkeypatch):
    """before는 배타적, after는 포함 - 구글 경로와 같은 규칙."""
    items = [
        _item("너무 최신", "https://a.com/1", "Mon, 28 Sep 2026 09:00:00 +0900"),  # before 이상 -> 제외
        _item("창 안 1", "https://b.com/2", "Sat, 26 Sep 2026 09:00:00 +0900"),
        _item("창 안 2", "https://c.com/3", "Mon, 21 Sep 2026 09:00:00 +0900"),   # after 당일 -> 포함
        _item("너무 과거", "https://d.com/4", "Sun, 20 Sep 2026 09:00:00 +0900"),  # after 미만 -> 중단
    ]
    monkeypatch.setattr(tnc.requests, "get", lambda *a, **k: _FakeResp({"items": items}))

    got = tnc.search_naver_news_kr("조선업", date(2026, 9, 21), date(2026, 9, 28))

    assert [g["title"] for g in got] == ["창 안 1", "창 안 2"]
    assert got[0]["published_at"] == "2026-09-26"


def test_제목의_태그와_엔티티를_정리한다(naver_env, monkeypatch):
    items = [_item("<b>조선</b>업 &quot;수주&quot; &amp; 실적",
                   "https://a.com/1", "Sat, 26 Sep 2026 09:00:00 +0900")]
    monkeypatch.setattr(tnc.requests, "get", lambda *a, **k: _FakeResp({"items": items}))

    got = tnc.search_naver_news_kr("조선업", date(2026, 9, 21), date(2026, 9, 28))

    assert got[0]["title"] == '조선업 "수주" & 실적'


def test_source는_원문_도메인을_쓴다(naver_env, monkeypatch):
    items = [_item("기사", "https://www.hankyung.com/article/123",
                   "Sat, 26 Sep 2026 09:00:00 +0900")]
    monkeypatch.setattr(tnc.requests, "get", lambda *a, **k: _FakeResp({"items": items}))

    got = tnc.search_naver_news_kr("조선업", date(2026, 9, 21), date(2026, 9, 28))

    assert got[0]["source"] == "www.hankyung.com"


def test_조회_실패는_0건이_아니라_예외다(naver_env, monkeypatch):
    """실패를 0건으로 기록하면 그 값이 기준선에 그대로 남는다 - 구글 경로와 같은 규칙."""
    monkeypatch.setattr(tnc, "FETCH_BACKOFF_SEC", [])   # 테스트에서 재시도 대기 제거
    monkeypatch.setattr(tnc.requests, "get", lambda *a, **k: _FakeResp({}, status=500))

    with pytest.raises(RuntimeError, match="네이버 뉴스 조회 실패"):
        tnc.search_naver_news_kr("조선업", date(2026, 9, 21), date(2026, 9, 28))


def test_키가_있으면_한국_수집이_네이버로_간다(naver_env, monkeypatch):
    """collect_theme_news의 소스 선택 - 키를 빼면 즉시 구글로 되돌아가야 한다."""
    called = {}

    def fake_naver(kw, after, before, limit=tnc.RESULT_LIMIT):
        called["source"] = "naver"
        return []

    def fake_google(kw, after, before, limit=tnc.RESULT_LIMIT):
        called["source"] = "google"
        return []

    monkeypatch.setattr(tnc, "search_naver_news_kr", fake_naver)
    monkeypatch.setattr(tnc, "search_google_news_kr", fake_google)
    monkeypatch.setattr(tnc, "KEYWORD_SLEEP_SEC", 0)

    tnc.collect_theme_news(["조선업"], date(2026, 9, 21), date(2026, 9, 28), market="KR")
    assert called["source"] == "naver"

    monkeypatch.delenv("NAVER_CLIENT_ID")
    tnc.collect_theme_news(["조선업"], date(2026, 9, 21), date(2026, 9, 28), market="KR")
    assert called["source"] == "google"


def _feed(per_day: int, days: int, newest: datetime) -> list[dict]:
    """newest부터 과거로 하루 per_day건씩 고르게 깔린 최신순 기사."""
    step = timedelta(days=1) / per_day
    return [_item(f"t{i}", f"https://x.com/{i}", format_datetime(newest - step * (i + 1)))
            for i in range(per_day * days)]


def _paged_get(feed: list[dict]):
    def get(url, params, headers, timeout):
        start = params["start"]
        return _FakeResp({"items": feed[start - 1:start - 1 + params["display"]]})
    return get


@pytest.mark.parametrize("per_day", [150, 300, 500])
def test_기사가_많을수록_적게_세지_않는다(naver_env, monkeypatch, per_day):
    """2026-10-04 회귀: 하루씩 나눠 다시 세던 때는 하루 500건 키워드가 주 200건으로
    세어졌다(start 상한 때문에 앞쪽 날짜에 못 닿음). 상한에 걸려도 최소 800건은 세고
    상한으로 표시돼야 한다."""
    monday_7am = datetime(2026, 10, 5, 7, 0, tzinfo=timezone(timedelta(hours=9)))
    monkeypatch.setattr(tnc.requests, "get", _paged_get(_feed(per_day, 14, monday_7am)))
    monkeypatch.setattr(tnc, "KEYWORD_SLEEP_SEC", 0)
    monkeypatch.setattr(tnc.time, "sleep", lambda s: None)

    _, stats = tnc.collect_theme_news(["kw"], date(2026, 9, 28), date(2026, 10, 5), market="KR")

    assert stats["per_keyword"]["kw"] >= 800
    assert stats["saturated_keywords"] == ["kw"]
    assert stats["expanded_keywords"] == []   # 네이버는 하루 단위로 나누지 않는다


def test_상한_아래면_전부_세고_상한_표시가_없다(naver_env, monkeypatch):
    monday_7am = datetime(2026, 10, 5, 7, 0, tzinfo=timezone(timedelta(hours=9)))
    monkeypatch.setattr(tnc.requests, "get", _paged_get(_feed(50, 14, monday_7am)))
    monkeypatch.setattr(tnc, "KEYWORD_SLEEP_SEC", 0)
    monkeypatch.setattr(tnc.time, "sleep", lambda s: None)

    _, stats = tnc.collect_theme_news(["kw"], date(2026, 9, 28), date(2026, 10, 5), market="KR")

    assert stats["per_keyword"]["kw"] == 350
    assert stats["saturated_keywords"] == []


def test_결과_끝까지_읽으면_truncated가_아니다(naver_env, monkeypatch):
    items = [_item("창 안", "https://b.com/2", "Sat, 26 Sep 2026 09:00:00 +0900")]
    monkeypatch.setattr(tnc.requests, "get", lambda *a, **k: _FakeResp({"items": items}))

    got = tnc.search_naver_news_kr("조선업", date(2026, 9, 21), date(2026, 9, 28))

    assert len(got) == 1 and got.truncated is False
