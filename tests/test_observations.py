"""관찰 노트 - 회고 시점 계산과 기대 결과(사실만, 계산 불가는 None)."""
import json
import sqlite3

from src.db.observations import (due_checkpoints, ensure_schema, expect_results, fill_review_returns,
                                 insert_review, load_open_observations, load_refill_candidates)


def test_due_checkpoints():
    assert due_checkpoints("2026-09-28", "2026-10-19", set()) == []
    assert due_checkpoints("2026-09-28", "2026-10-26", set()) == [4]
    assert due_checkpoints("2026-09-28", "2026-12-21", {4}) == [12]
    assert due_checkpoints("2026-09-28", "2027-01-04", {4, 12}) == []


def test_theme_expects_use_current_arrows_and_na_is_none():
    now = {"news_arrow": "up1", "price_arrow": "flat", "earn_arrow": "na"}
    r = expect_results("theme", ["news_up", "price_up", "earn_hold", "unsure"], now)
    assert r == {"news_up": True, "price_up": False, "earn_hold": None}


def test_stock_expects():
    now = {"ret_since": 0.05, "index_ret_since": 0.02, "earn_status": "insufficient",
           "themes": [{"news_arrow": "na"}, {"news_arrow": "down"}]}
    r = expect_results("stock", ["price_up", "earn_hold", "news_up"], now)
    assert r == {"price_up": True, "earn_hold": None, "news_up": False}
    assert expect_results("stock", ["price_up"], {"ret_since": None, "index_ret_since": 0.01}) == {"price_up": None}
    assert expect_results("stock", ["news_up"], {"themes": [{"news_arrow": "na"}]}) == {"news_up": None}


def test_review_written_once():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    conn.execute("INSERT INTO observations (created_at, kind, market, theme_id, hypothesis, expects, week_start, snapshot) "
                 "VALUES ('2026-10-05T01:00', 'theme', 'KR', 'ai', '가설', ?, '2026-09-28', '{}')", (json.dumps(["news_up"]),))
    insert_review(conn, 1, 4, "t1", "2026-10-26", {"news_arrow": "up1"}, {"news_up": True})
    insert_review(conn, 1, 4, "t2", "2026-10-26", {"news_arrow": "down"}, {"news_up": False})   # 덮어쓰지 않음
    row = conn.execute("SELECT reviewed_at, expect_results FROM observation_reviews").fetchone()
    assert row == ("t1", '{"news_up": true}')
    assert load_open_observations(conn)[0]["done"] == {4}


def test_down_expects_and_legacy_earn_hold():
    now = {"news_arrow": "down", "earn_arrow": "flat", "price_arrow": "up2"}
    r = expect_results("theme", ["news_down", "earn_down", "price_down", "earn_hold"], now)
    assert r == {"news_down": True, "earn_down": False, "price_down": False, "earn_hold": False}
    stock = {"ret_since": -0.03, "index_ret_since": 0.01, "earn_status": "not_improved",
             "themes": [{"news_arrow": "down"}, {"news_arrow": "up1"}]}
    assert expect_results("stock", ["price_down", "earn_down", "news_down", "earn_up"], stock) == \
        {"price_down": True, "earn_down": True, "news_down": True, "earn_up": False}


def test_refill_only_missing_and_unjudged():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    for i, t in enumerate(["AAA", "BBB", "CCC"], start=1):
        conn.execute("INSERT INTO observations (created_at, kind, market, ticker, hypothesis, expects, week_start, snapshot) "
                     "VALUES ('2026-10-05T01:00', 'stock', 'US', ?, 'h', '[\"price_up\"]', '2026-09-28', '{}')", (t,))
    insert_review(conn, 1, 4, "2026-11-01T23:00", "2026-10-26", {"ret_since": None, "index_ret_since": 0.01}, {"price_up": None})
    insert_review(conn, 2, 4, "2026-11-01T23:00", "2026-10-26", {"ret_since": 0.05, "index_ret_since": 0.01}, {"price_up": True})
    insert_review(conn, 3, 4, "2026-11-01T23:00", "2026-10-26", {"ret_since": None, "index_ret_since": None}, {"price_up": None})
    conn.execute("UPDATE observation_reviews SET verdict = 'unclear' WHERE observation_id = 3")
    cands = load_refill_candidates(conn)
    assert [c["observation_id"] for c in cands] == [1]          # 값 있는 2, 판단 끝난 3은 제외
    fill_review_returns(conn, 1, 4, {"ret_since": 0.03, "index_ret_since": 0.01}, {"price_up": True})
    assert conn.execute("SELECT expect_results FROM observation_reviews WHERE observation_id = 1").fetchone()[0] == '{"price_up": true}'
    assert load_refill_candidates(conn) == []


def test_return_since_uses_until(monkeypatch):
    import sys, types
    from datetime import date
    import pandas as pd
    idx = pd.to_datetime(["2026-10-02", "2026-10-05", "2026-10-30", "2026-11-06"])
    fake = types.SimpleNamespace(Ticker=lambda s: types.SimpleNamespace(
        history=lambda **k: pd.DataFrame({"Close": [100.0, 102.0, 110.0, 120.0]}, index=idx)))
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("ro", Path(__file__).resolve().parent.parent / "scripts" / "review_observations.py")
    ro = importlib.util.module_from_spec(spec); spec.loader.exec_module(ro)
    assert abs(ro.return_since("X", date(2026, 10, 5)) - (120 / 102 - 1)) < 1e-9          # 오늘(마지막)까지
    assert abs(ro.return_since("X", date(2026, 10, 5), date(2026, 11, 1)) - (110 / 102 - 1)) < 1e-9   # 회고일 직전 종가
    assert abs(ro.return_since("X", date(2026, 10, 4)) - (120 / 100 - 1)) < 1e-9          # 작성일 직전 거래일
