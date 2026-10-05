"""관찰 노트 (2026-10-05) - 테마·종목에 가설을 한 줄 남기고 4주·12주 뒤 "그때와 지금"을 나란히 놓는다.

원칙:
- 가설·그때 값(snapshot)은 한 번 쓰면 고치지 않는다(이력 테이블은 덮어쓰지 않는다). 사람이 나중에 붙이는 것은
  회고의 판단(verdict)과 배운 점(lesson)뿐이다.
- 판정은 사람이 한다. 툴은 고른 기대(뉴스 ↑ 등)가 실제로 일어났는지 사실만 적는다 - 계산 불가는 None(데이터부족).
- 숫자는 전부 DB·시세 값. LLM 없음.

쓰는 곳: frontend /api/notes (작성·판단 저장·조회, 같은 DDL), scripts/review_observations.py (주간 회고 채우기),
scripts/generate_weekly_briefing.py (회고 도착 줄).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

OBSERVATIONS_DDL = """
CREATE TABLE IF NOT EXISTS observations (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at  TEXT NOT NULL,
  kind        TEXT NOT NULL,          -- theme | stock
  market      TEXT NOT NULL,
  theme_id    TEXT,
  ticker      TEXT,
  hypothesis  TEXT NOT NULL,
  expects     TEXT NOT NULL,          -- JSON 배열: {news,earn,price}_{up,down} / unsure (예전 earn_hold = earn_up)
  week_start  TEXT NOT NULL,          -- 작성 시점의 신호 주(월요일)
  snapshot    TEXT NOT NULL           -- JSON: 그때 값
)
"""

OBSERVATION_REVIEWS_DDL = """
CREATE TABLE IF NOT EXISTS observation_reviews (
  observation_id INTEGER NOT NULL,
  checkpoint     INTEGER NOT NULL,    -- 4 | 12 (주)
  reviewed_at    TEXT NOT NULL,
  week_start     TEXT NOT NULL,       -- 회고 값의 신호 주
  snapshot       TEXT NOT NULL,       -- JSON: 지금 값 (+ 종목은 작성 이후 수익률·지수 수익률)
  expect_results TEXT NOT NULL,       -- JSON: {기대: true/false/null}
  verdict        TEXT,                -- 사람: right / wrong / unclear
  lesson         TEXT,                -- 사람: 배운 점 한 줄
  judged_at      TEXT,
  PRIMARY KEY (observation_id, checkpoint)
)
"""

CHECKPOINTS = (4, 12)
# 축마다 ↑ 또는 ↓ 하나(2026-10-05 사용자 의견 - 하향 가설도 남길 수 있게). earn_hold는 첫 버전 키로 earn_up과 같다.
EXPECTS = ("news_up", "news_down", "earn_up", "earn_down", "price_up", "price_down", "unsure", "earn_hold")
UP = ("up1", "up2")


def ensure_schema(conn) -> None:
    conn.execute(OBSERVATIONS_DDL)
    conn.execute(OBSERVATION_REVIEWS_DDL)
    conn.commit()


def due_checkpoints(created_week: str, current_week: str, done: set[int]) -> list[int]:
    """작성 주 + N주 이상 지났고 아직 회고가 없는 체크포인트."""
    c = date.fromisoformat(created_week)
    now = date.fromisoformat(current_week)
    return [n for n in CHECKPOINTS if n not in done and now >= c + timedelta(weeks=n)]


def _dir(a: str | None, want: str) -> bool | None:
    """테마 화살표가 기대 방향인지. up = ↑/↑↑, down = ↓. 계산 불가(na·없음)는 None."""
    if a is None or a == "na":
        return None
    return a in UP if want == "up" else a == "down"


def expect_results(kind: str, expects: list[str], now: dict) -> dict[str, bool | None]:
    """고른 기대가 회고 시점에 일어났는지. 사실만, 계산 불가는 None.

    테마: {축}_up = 그 축이 지금 ↑, {축}_down = 지금 ↓.
    종목: price_up/down = 작성 이후 수익률이 같은 기간 지수 수익률보다 높음/낮음,
          news_up/down = 사업 소속 테마 중 하나라도 뉴스 ↑/↓ (전부 na면 None),
          earn_up/down = 지금 실적 판정이 '중앙값 초과'/'미달'."""
    out: dict[str, bool | None] = {}
    for e in expects:
        if e == "unsure":
            continue
        key = "earn_up" if e == "earn_hold" else e
        axis, _, want = key.partition("_")
        if want not in ("up", "down") or axis not in ("news", "earn", "price"):
            continue
        if kind == "theme":
            out[e] = _dir(now.get(f"{axis}_arrow"), want)
        elif axis == "price":
            r, i = now.get("ret_since"), now.get("index_ret_since")
            out[e] = None if r is None or i is None else (r > i if want == "up" else r < i)
        elif axis == "news":
            vals = [_dir(t.get("news_arrow"), want) for t in now.get("themes") or []]
            known = [v for v in vals if v is not None]
            out[e] = None if not known else any(known)
        else:
            st = now.get("earn_status")
            out[e] = None if st in (None, "insufficient") else st == ("improved" if want == "up" else "not_improved")
    return out


# ── 지금 값 만들기 (회고·작성 공통 모양) ──────────────────────────────────────

def theme_snapshot(conn, theme_id: str, market: str) -> dict | None:
    row = conn.execute(
        "SELECT week_start, news_arrow, earn_arrow, price_arrow, label, price_excess, news_count, earn_ratio "
        "FROM theme_signals WHERE theme_id = ? AND market = ? ORDER BY week_start DESC LIMIT 1",
        (theme_id, market),
    ).fetchone()
    if not row:
        return None
    keys = ("week_start", "news_arrow", "earn_arrow", "price_arrow", "label", "price_excess", "news_count", "earn_ratio")
    return dict(zip(keys, row))


def stock_snapshot(conn, ticker: str, market: str) -> dict:
    """종목 하나의 지금 값: 사업 소속 테마들의 세 축, 최근 기업별 값, 워치리스트 재무 꼬리표."""
    themes = []
    for (tid,) in conn.execute(
            "SELECT DISTINCT theme_id FROM theme_members WHERE ticker = ? AND market = ? AND approved = 1",
            (ticker, market)).fetchall():
        run = conn.execute("SELECT MAX(run_id) FROM theme_members WHERE theme_id = ? AND market = ? AND approved = 1",
                           (tid, market)).fetchone()[0]
        link = conn.execute("SELECT linkage FROM theme_members WHERE theme_id = ? AND market = ? AND run_id = ? "
                            "AND ticker = ? AND approved = 1", (tid, market, run, ticker)).fetchone()
        if not link or link[0] not in ("direct", "partial"):
            continue
        s = theme_snapshot(conn, tid, market)
        if s:
            themes.append({"theme_id": tid, **{k: s[k] for k in ("news_arrow", "earn_arrow", "price_arrow", "label")}})
    snap: dict = {"themes": themes, "price_ret_4w": None, "earn_status": None, "rev_yoy": None,
                  "piotroski": None, "valuation_tier": None, "growth_tier": None, "week_start": None}
    try:
        m = conn.execute(
            "SELECT week_start, price_ret, earn_status, rev_yoy FROM theme_member_signals "
            "WHERE ticker = ? AND market = ? ORDER BY week_start DESC LIMIT 1", (ticker, market)).fetchone()
        if m:
            snap.update(week_start=m[0], price_ret_4w=m[1], earn_status=m[2], rev_yoy=m[3])
    except Exception:
        pass
    try:
        w = conn.execute("SELECT piotroski, valuation_tier, growth_tier FROM watchlist_candidates "
                         "WHERE market = ? AND symbol = ?", (market, ticker)).fetchone()
        if w:
            snap.update(piotroski=w[0], valuation_tier=w[1], growth_tier=w[2])
    except Exception:
        pass
    return snap


def load_open_observations(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT o.id, o.created_at, o.kind, o.market, o.theme_id, o.ticker, o.expects, o.week_start, "
        "GROUP_CONCAT(r.checkpoint) FROM observations o "
        "LEFT JOIN observation_reviews r ON r.observation_id = o.id GROUP BY o.id").fetchall()
    out = []
    for oid, created, kind, market, tid, ticker, expects, week, done in rows:
        done_set = {int(x) for x in str(done).split(",")} if done else set()
        out.append({"id": oid, "created_at": created, "kind": kind, "market": market, "theme_id": tid,
                    "ticker": ticker, "expects": json.loads(expects or "[]"), "week_start": week, "done": done_set})
    return out


def insert_review(conn, observation_id: int, checkpoint: int, reviewed_at: str, week_start: str,
                  snapshot: dict, results: dict) -> None:
    """INSERT OR IGNORE - 같은 체크포인트 회고는 한 번만 쓴다(덮어쓰지 않음)."""
    conn.execute(
        "INSERT OR IGNORE INTO observation_reviews "
        "(observation_id, checkpoint, reviewed_at, week_start, snapshot, expect_results) VALUES (?, ?, ?, ?, ?, ?)",
        (observation_id, checkpoint, reviewed_at, week_start,
         json.dumps(snapshot, ensure_ascii=False), json.dumps(results)),
    )


def load_refill_candidates(conn) -> list[dict]:
    """종목 회고 중 시세 조회 실패로 수익률이 빈 것(아직 판단 전). 다음 주 회고 작업이 빈 값만 채운다."""
    rows = conn.execute(
        "SELECT r.observation_id, r.checkpoint, r.reviewed_at, r.snapshot, o.created_at, o.market, o.ticker, o.expects "
        "FROM observation_reviews r JOIN observations o ON o.id = r.observation_id "
        "WHERE o.kind = 'stock' AND r.verdict IS NULL").fetchall()
    out = []
    for oid, cp, reviewed_at, snap, created, market, ticker, expects in rows:
        snap_d = json.loads(snap or "{}")
        if snap_d.get("ret_since") is not None and snap_d.get("index_ret_since") is not None:
            continue
        out.append({"observation_id": oid, "checkpoint": cp, "reviewed_at": reviewed_at, "snapshot": snap_d,
                    "created_at": created, "market": market, "ticker": ticker, "expects": json.loads(expects or "[]")})
    return out


def fill_review_returns(conn, observation_id: int, checkpoint: int, snapshot: dict, results: dict) -> None:
    """빈 수익률을 채운 snapshot과 다시 낸 기대 결과로 갱신 - 판단 전인 회고만(사람이 판단한 뒤엔 건드리지 않는다)."""
    conn.execute(
        "UPDATE observation_reviews SET snapshot = ?, expect_results = ? "
        "WHERE observation_id = ? AND checkpoint = ? AND verdict IS NULL",
        (json.dumps(snapshot, ensure_ascii=False), json.dumps(results), observation_id, checkpoint),
    )
