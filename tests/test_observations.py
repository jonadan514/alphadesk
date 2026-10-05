"""관찰 노트 - 회고 시점 계산과 기대 결과(사실만, 계산 불가는 None)."""
import json
import sqlite3

from src.db.observations import (due_checkpoints, ensure_schema, expect_results, insert_review,
                                 load_open_observations)


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
