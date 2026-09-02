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


def insert_theme_news_bulk(conn, theme_id: str, market: str, week_start: str,
                            articles: list[dict], chunk_size: int = 200) -> None:
    """articles를 chunk_size 단위로 묶어 한 번의 INSERT로 저장한다.

    기사마다 insert_theme_news()를 개별 호출하면 Turso HTTP 클라이언트는
    호출 하나마다 실제 HTTP 왕복을 하므로(Phase 0 §3에서 겪은 것과 같은
    문제), 뉴스가 많은 테마 하나의 한 주 분량(수백 건)만으로도 왕복이
    폭증한다. get_cached_financials_bulk()와 같은 처방 - 여러 값을 한
    INSERT 문의 VALUES에 묶는다."""
    if not articles:
        return
    for i in range(0, len(articles), chunk_size):
        chunk = articles[i:i + chunk_size]
        placeholders = ", ".join(["(?, ?, ?, ?, ?, ?, ?, ?)"] * len(chunk))
        params: list = []
        for a in chunk:
            params.extend([
                theme_id, market, a["_url_hash"], a["title"], a["url"],
                a["published_at"], a["source"], week_start,
            ])
        conn.execute(
            "INSERT OR IGNORE INTO theme_news "
            "(theme_id, market, url_hash, title, url, published_at, source, week_start) "
            f"VALUES {placeholders}",
            tuple(params),
        )


def get_prior_news_counts(conn, theme_id: str, market: str, week_start: str, weeks: int = 4) -> list[int]:
    """week_start 이전 주들의 news_count를 최대 weeks개 가져온다 (baseline 계산용).
    news_count가 NULL인 행(계산 실패)은 제외한다.

    Turso HTTP 클라이언트(_TursoConn)는 정수 컬럼 값을 문자열로 반환한다
    (Hrana 프로토콜이 64비트 정밀도 손실 방지를 위해 정수를 문자열로 실어
    보내는데, _TursoConn.fetchall()이 타입 변환 없이 그대로 넘김) - 로컬
    sqlite3 폴백은 이미 int를 반환하므로 int()가 양쪽 다 안전하게 처리한다.
    """
    rows = conn.execute(
        """
        SELECT news_count FROM theme_signals
        WHERE theme_id = ? AND market = ? AND week_start < ? AND news_count IS NOT NULL
        ORDER BY week_start DESC LIMIT ?
        """,
        (theme_id, market, week_start, weeks),
    ).fetchall()
    return [int(r[0]) for r in rows]


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


def upsert_earn_signal(conn, theme_id: str, market: str, week_start: str,
                        earn_members: int, earn_improved: int, earn_insufficient: int,
                        earn_ratio: float | None, earn_arrow: str, earn_as_of: str | None,
                        member_count: int, mapping_run_id: str, computed_at: str) -> None:
    """theme_signals에 실적 축만 채워 넣는다(뉴스/주가 축은 건드리지 않음).

    실적 축은 주간 신호가 아니라 분기에 한 번만 바뀐다(SPEC §3.4) - 그래도
    매주 도는 파이프라인이 같은 값을 반복해서 그 주 행에 채워 넣는다. 그래야
    화면이 "이번 주 상태"를 보여줄 때 세 축이 다 채워진 최신 행 하나만 보면
    되고, earn_as_of로 "이 값은 지난 분기 것"임을 표시할 수 있다."""
    conn.execute(
        """
        INSERT INTO theme_signals
          (theme_id, market, week_start, earn_members, earn_improved, earn_insufficient,
           earn_ratio, earn_arrow, earn_as_of, member_count, mapping_run_id, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(theme_id, market, week_start) DO UPDATE SET
          earn_members = excluded.earn_members,
          earn_improved = excluded.earn_improved,
          earn_insufficient = excluded.earn_insufficient,
          earn_ratio = excluded.earn_ratio,
          earn_arrow = excluded.earn_arrow,
          earn_as_of = excluded.earn_as_of,
          member_count = excluded.member_count,
          mapping_run_id = excluded.mapping_run_id,
          computed_at = excluded.computed_at
        """,
        (theme_id, market, week_start, earn_members, earn_improved, earn_insufficient,
         earn_ratio, earn_arrow, earn_as_of, member_count, mapping_run_id, computed_at),
    )


def upsert_price_signal(conn, theme_id: str, market: str, week_start: str,
                         price_median_ret: float | None, price_index_ret: float | None,
                         price_excess: float | None, price_arrow: str,
                         member_count: int, mapping_run_id: str, computed_at: str) -> None:
    """theme_signals에 주가 축만 채워 넣는다(뉴스/실적 축은 건드리지 않음)."""
    conn.execute(
        """
        INSERT INTO theme_signals
          (theme_id, market, week_start, price_median_ret, price_index_ret, price_excess,
           price_arrow, member_count, mapping_run_id, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(theme_id, market, week_start) DO UPDATE SET
          price_median_ret = excluded.price_median_ret,
          price_index_ret = excluded.price_index_ret,
          price_excess = excluded.price_excess,
          price_arrow = excluded.price_arrow,
          member_count = excluded.member_count,
          mapping_run_id = excluded.mapping_run_id,
          computed_at = excluded.computed_at
        """,
        (theme_id, market, week_start, price_median_ret, price_index_ret, price_excess,
         price_arrow, member_count, mapping_run_id, computed_at),
    )


def get_approved_theme_members(conn, theme_id: str, market: str,
                                linkages: tuple[str, ...] = ("direct", "partial")) -> list[dict]:
    """SPEC §5 - "현재 유효 매핑은 최신 run_id + approved=1로 조회한다"를 그대로
    구현. approved=1이라고 전부 모으면, 나중에 분기 재매핑이 또 승인됐을 때
    예전 run의 승인 행과 중복 집계된다 - 가장 최근 run_id 하나로 고정한다.
    linkage 필터는 SPEC §3.2 기본값(peripheral 제외)."""
    latest_run = conn.execute(
        "SELECT MAX(run_id) FROM theme_members WHERE theme_id = ? AND market = ? AND approved = 1",
        (theme_id, market),
    ).fetchone()
    if not latest_run or not latest_run[0]:
        return []
    run_id = latest_run[0]

    placeholders = ",".join("?" for _ in linkages)
    rows = conn.execute(
        f"""
        SELECT ticker FROM theme_members
        WHERE theme_id = ? AND market = ? AND run_id = ? AND approved = 1 AND linkage IN ({placeholders})
        """,
        (theme_id, market, run_id, *linkages),
    ).fetchall()
    return [{"ticker": r[0], "run_id": run_id} for r in rows]
