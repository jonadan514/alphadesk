"""Phase A-3~5: 테마 신호(theme_news, theme_signals) 스키마 + 쓰기 함수.

SPEC: docs/radar/SPEC_phase_a_signals.md §1
"""
from __future__ import annotations

THEME_NEWS_DDL = """
CREATE TABLE IF NOT EXISTS theme_news (
  theme_id     TEXT NOT NULL,
  market       TEXT NOT NULL,
  url_hash     TEXT NOT NULL,
  title        TEXT,
  url          TEXT,
  published_at TEXT,
  source       TEXT,
  week_start   TEXT NOT NULL,
  PRIMARY KEY (theme_id, market, url_hash)
)
"""

# SPEC 원안(§1.1)엔 news_backfilled 컬럼이 없지만, §2.4가 "backfilled=true 플래그를
# 남기고 첫 4주 판정은 참고용으로만 본다"고 명시적으로 요구해서 추가함 - SPEC 본문과
# 스키마 사이의 누락을 채운 것.
THEME_SIGNALS_DDL = """
CREATE TABLE IF NOT EXISTS theme_signals (
  theme_id          TEXT NOT NULL,
  market            TEXT NOT NULL,
  week_start        TEXT NOT NULL,

  news_count        INTEGER,
  news_baseline     REAL,
  news_ratio        REAL,
  news_arrow        TEXT,
  news_backfilled   INTEGER DEFAULT 0,

  earn_members      INTEGER,
  earn_improved     INTEGER,
  earn_insufficient INTEGER,
  earn_ratio        REAL,
  earn_arrow        TEXT,
  earn_as_of        TEXT,

  price_median_ret  REAL,
  price_index_ret   REAL,
  price_excess      REAL,
  price_arrow       TEXT,

  label             TEXT,
  member_count      INTEGER,
  mapping_run_id    TEXT,
  computed_at       TEXT NOT NULL,

  PRIMARY KEY (theme_id, market, week_start)
)
"""


def ensure_schema(conn) -> None:
    conn.execute(THEME_NEWS_DDL)
    conn.execute(THEME_SIGNALS_DDL)
    conn.commit()


def insert_theme_news(conn, theme_id: str, market: str, url_hash: str, title: str,
                       url: str, published_at: str, source: str, week_start: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO theme_news
          (theme_id, market, url_hash, title, url, published_at, source, week_start)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (theme_id, market, url_hash, title, url, published_at, source, week_start),
    )


def get_prior_news_counts(conn, theme_id: str, market: str, week_start: str, weeks: int = 4) -> list[int]:
    """week_start 이전 주들의 news_count를 최대 weeks개 가져온다 (baseline 계산용).
    news_count가 NULL인 행(계산 실패)은 제외한다."""
    rows = conn.execute(
        """
        SELECT news_count FROM theme_signals
        WHERE theme_id = ? AND market = ? AND week_start < ? AND news_count IS NOT NULL
        ORDER BY week_start DESC LIMIT ?
        """,
        (theme_id, market, week_start, weeks),
    ).fetchall()
    return [r[0] for r in rows]


def upsert_news_signal(conn, theme_id: str, market: str, week_start: str,
                        news_count: int, news_baseline: float | None, news_ratio: float | None,
                        news_arrow: str, backfilled: bool, computed_at: str) -> None:
    """theme_signals에 뉴스 축만 채워 넣는다. 실적/주가 축(Phase A-4/A-5)이
    나중에 같은 행을 UPDATE하므로 여기서는 뉴스 관련 컬럼만 갱신하고 나머지는
    건드리지 않는다."""
    conn.execute(
        """
        INSERT INTO theme_signals
          (theme_id, market, week_start, news_count, news_baseline, news_ratio,
           news_arrow, news_backfilled, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(theme_id, market, week_start) DO UPDATE SET
          news_count = excluded.news_count,
          news_baseline = excluded.news_baseline,
          news_ratio = excluded.news_ratio,
          news_arrow = excluded.news_arrow,
          news_backfilled = excluded.news_backfilled,
          computed_at = excluded.computed_at
        """,
        (theme_id, market, week_start, news_count, news_baseline, news_ratio,
         news_arrow, 1 if backfilled else 0, computed_at),
    )
