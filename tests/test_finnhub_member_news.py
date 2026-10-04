"""미국 뉴스 축 - Finnhub 소속 기업 뉴스 건수 (theme_news_collector.collect_member_news).

네트워크를 타지 않는다. 핵심 규칙: (1) 여러 소속에 걸린 같은 기사는 한 번만 센다
(2) 여러 테마에 있는 종목은 한 번만 조회한다 (3) 조회 실패는 0건이 아니라 failed로 남는다
(4) 응답이 상한 근처면 saturated로 표시한다 (5) 창 밖 날짜는 버린다.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

import src.collectors.theme_news_collector as tnc

AFTER, BEFORE = date(2026, 9, 28), date(2026, 10, 5)


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc).timestamp())


class _Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    monkeypatch.setattr(tnc, "FINNHUB_SLEEP_SEC", 0)
    monkeypatch.setattr(tnc, "FETCH_BACKOFF_SEC", [])


def _fake(feeds, calls):
    def get(url, params, timeout):
        calls.append(params["symbol"])
        feed = feeds[params["symbol"]]
        return feed if isinstance(feed, _Resp) else _Resp(feed)
    return get


def test_겹친_기사는_한번만_종목은_한번만_조회(env, monkeypatch):
    shared = {"id": 1, "headline": "ETN and PWR", "url": "https://x.com/a", "datetime": _ts(date(2026, 9, 29)), "source": "x"}
    feeds = {
        "ETN": [shared, {"id": 2, "headline": "b", "url": "https://x.com/b", "datetime": _ts(date(2026, 9, 30))}],
        "PWR": [shared],
    }
    calls: list = []
    monkeypatch.setattr(tnc.requests, "get", _fake(feeds, calls))
    res = tnc.collect_member_news({"power_grid": ["ETN", "PWR"], "datacenter_power": ["ETN"]}, AFTER, BEFORE)
    arts, st = res["power_grid"]
    assert len(arts) == 2 and st["raw_total"] == 3
    assert sorted(calls) == ["ETN", "PWR"]          # ETN은 두 테마에 있어도 한 번만
    assert len(res["datacenter_power"][0]) == 2


def test_조회_실패는_0건이_아니라_failed(env, monkeypatch):
    feeds = {"ETN": _Resp({}, 500), "PWR": []}
    monkeypatch.setattr(tnc.requests, "get", _fake(feeds, []))
    arts, st = tnc.collect_member_news({"power_grid": ["ETN", "PWR"]}, AFTER, BEFORE)["power_grid"]
    assert st["failed_members"] and st["failed_members"][0].startswith("ETN")
    assert st["per_member"] == {"PWR": 0}


def test_창_밖_날짜는_버리고_상한이면_표시(env, monkeypatch):
    many = [{"id": i, "headline": "h", "url": f"https://x.com/{i}", "datetime": _ts(date(2026, 9, 29))}
            for i in range(tnc.FINNHUB_CAP)]
    old = {"id": 999, "headline": "old", "url": "https://x.com/old", "datetime": _ts(date(2026, 9, 20))}
    monkeypatch.setattr(tnc.requests, "get", _fake({"BA": many + [old]}, []))
    arts, st = tnc.collect_member_news({"defense": ["BA"]}, AFTER, BEFORE)["defense"]
    assert len(arts) == tnc.FINNHUB_CAP and st["saturated_members"] == ["BA"]


def test_클래스_주식_표기_변환(env, monkeypatch):
    calls: list = []
    monkeypatch.setattr(tnc.requests, "get", _fake({"MOG.A": []}, calls))
    tnc.collect_member_news({"defense": ["MOG-A"]}, AFTER, BEFORE)
    assert calls == ["MOG.A"]
