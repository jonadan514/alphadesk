"""Turso 일시 오류 재시도와 뉴스 대량 저장 쪼개기 (2026-10-05 disk I/O error 대책)."""
import sqlite3
from unittest import mock

import pytest

import src.db.data_store as ds
from src.db.theme_signals import ensure_schema, insert_theme_news_bulk


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


def _ok():
    return _Resp(200, {"results": [{"type": "ok", "response": {"result": {"rows": []}}}]})


def _err(msg):
    return _Resp(200, {"results": [{"type": "error", "error": {"message": msg}}]})


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)


def test_transient_error_is_retried_then_succeeds():
    conn = ds._TursoConn("libsql://x.turso.io", "t")
    with mock.patch("requests.post", side_effect=[_err("SQLite error: disk I/O error"), _Resp(503, {}), _ok()]) as post:
        conn.execute("INSERT OR IGNORE INTO t VALUES (?)", (1,))
    assert post.call_count == 3


def test_gives_up_after_retries():
    conn = ds._TursoConn("libsql://x.turso.io", "t")
    with mock.patch("requests.post", return_value=_err("SQLite error: disk I/O error")) as post:
        with pytest.raises(ValueError, match="disk I/O"):
            conn.execute("SELECT 1")
    assert post.call_count == len(ds.RETRY_DELAYS) + 1


def test_real_errors_are_not_retried():
    conn = ds._TursoConn("libsql://x.turso.io", "t")
    with mock.patch("requests.post", return_value=_err("no such table: nope")) as post:
        with pytest.raises(ValueError, match="no such table"):
            conn.execute("SELECT * FROM nope")
    assert post.call_count == 1


class _FlakyConn:
    """묶음이 limit행보다 크면 실패하는 sqlite 래퍼."""
    def __init__(self, limit):
        self.db, self.limit, self.sizes = sqlite3.connect(":memory:"), limit, []
        ensure_schema(self.db)

    def execute(self, sql, params=()):
        if sql.startswith("INSERT OR IGNORE INTO theme_news"):
            n = len(params) // 8
            self.sizes.append(n)
            if n > self.limit:
                raise ValueError("SQLite error: disk I/O error")
        return self.db.execute(sql, params)


def _articles(n):
    return [{"_url_hash": f"h{i}", "title": f"t{i}", "url": f"u{i}", "published_at": None, "source": None}
            for i in range(n)]


def test_bulk_insert_splits_failed_chunk():
    c = _FlakyConn(limit=60)
    insert_theme_news_bulk(c, "ai", "KR", "2026-09-28", _articles(200))
    assert c.db.execute("SELECT COUNT(*) FROM theme_news").fetchone()[0] == 200
    assert max(s for s in c.sizes if s <= 60) <= 60


def test_bulk_insert_raises_when_even_small_chunks_fail():
    c = _FlakyConn(limit=0)
    with pytest.raises(ValueError):
        insert_theme_news_bulk(c, "ai", "KR", "2026-09-28", _articles(100))
