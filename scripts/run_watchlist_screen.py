"""워치리스트 스크리닝 — 주 1회 실행.

사용:
  python scripts/run_watchlist_screen.py           # US + KR 전체
  python scripts/run_watchlist_screen.py --market US
  python scripts/run_watchlist_screen.py --market KR
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from collectors.watchlist_collector import collect_universe
from analyzers.trap_filter import run_screen

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = ROOT / "output" / "data.db"

# SPEC_fundamentals_cache.md §3 — 매주 이만큼만 야후에서 실제로 갱신하고
# 나머지는 캐시를 읽는다. 환경변수로 노출(기본 60).
REFRESH_BUDGET = int(os.getenv("REFRESH_BUDGET", "60"))

# SPEC §6.3 — 이번 주 갱신 대상 중 (라이브 성공 + 캐시 폴백)/전체 시도 비율이
# 이 아래로 떨어지면 텔레그램 경고. job은 실패 처리하지 않는다.
CACHE_HIT_RATE_THRESHOLD = 0.70

CREATE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS watchlist_candidates (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  market              TEXT NOT NULL,
  symbol              TEXT NOT NULL,
  name                TEXT,
  market_cap          REAL,
  sector              TEXT,
  piotroski           INTEGER,
  debt_ratio          REAL,
  interest_coverage   REAL,
  cfo_positive_count  INTEGER,
  red_flags           TEXT,
  regime_fit          TEXT,
  roe                 REAL,
  current_price       REAL,
  rel_3m              REAL,
  rel_6m              REAL,
  fit_score           REAL,
  data_notes          TEXT,
  screened_at         TEXT NOT NULL,
  UNIQUE(market, symbol)
)"""
# rel_3m/rel_6m/fit_score는 모멘텀 랭킹(market_fit_scorer)이 없어지면서 항상 NULL —
# 순위 없는 재무 건전성 후보 목록으로 전환. current_price는 성적표 배치(진입가)와
# 페이퍼 포트폴리오 매수용으로 스크리닝 시점 가격을 남겨둔다.

# 매주 전체 교체 (이번 주 통과 종목만 유지 — 지난주 잔존 방지)
SCHEMA = f"""
DROP TABLE IF EXISTS watchlist_candidates;
{CREATE_TABLE_SQL};
CREATE INDEX IF NOT EXISTS idx_wl_market ON watchlist_candidates(market);
CREATE INDEX IF NOT EXISTS idx_wl_regime ON watchlist_candidates(regime_fit);
"""

# watchlist_candidates는 매주 통째로 교체돼 지난 주 데이터가 사라진다 — 성적표
# (compute_pick_returns.py)가 "N주 전 후보였던 종목이 그 뒤 얼마나 올랐는지"를
# 계산하려면 과거 스크리닝 결과가 남아있어야 하므로, 절대 DROP하지 않는 별도
# 이력 테이블에 매 회차 스크리닝 시점 스냅샷을 누적한다.
HISTORY_TABLE_SQL = """CREATE TABLE IF NOT EXISTS watchlist_candidate_history (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  screened_date  TEXT NOT NULL,
  market         TEXT NOT NULL,
  symbol         TEXT NOT NULL,
  name           TEXT,
  sector         TEXT,
  piotroski      INTEGER,
  regime_fit     TEXT,
  current_price  REAL,
  UNIQUE(screened_date, market, symbol)
)"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(HISTORY_TABLE_SQL)
    conn.commit()


def save_candidates(conn: sqlite3.Connection, candidates: list[dict]) -> None:
    now = datetime.utcnow().isoformat()
    rows = [
        (
            c["market"],
            c["symbol"],
            c["name"],
            c["market_cap"],
            c["sector"],
            c["piotroski"],
            c["debt_ratio"],
            c["interest_coverage"],
            c["cfo_positive_count"],
            json.dumps(c["red_flags"], ensure_ascii=False),
            c["regime_fit"],
            c.get("roe"),
            c.get("current_price"),
            c.get("rel_3m"),
            c.get("rel_6m"),
            c.get("fit_score"),
            json.dumps(c.get("data_notes") or {}, ensure_ascii=False),
            now,
        )
        for c in candidates
    ]
    conn.executemany(
        """
        INSERT INTO watchlist_candidates
          (market, symbol, name, market_cap, sector, piotroski,
           debt_ratio, interest_coverage, cfo_positive_count,
           red_flags, regime_fit, roe, current_price, rel_3m, rel_6m, fit_score, data_notes, screened_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.commit()
    logger.info("DB 저장 완료: %d 종목", len(rows))


def save_history(conn: sqlite3.Connection, candidates: list[dict], screened_date: str) -> None:
    rows = [
        (screened_date, c["market"], c["symbol"], c.get("name"), c.get("sector"),
         c.get("piotroski"), c.get("regime_fit"), c.get("current_price"))
        for c in candidates
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO watchlist_candidate_history
          (screened_date, market, symbol, name, sector, piotroski, regime_fit, current_price)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.commit()


def push_to_turso(candidates: list[dict]) -> None:
    """스크리닝 결과를 Turso에 upsert."""
    import urllib.error

    from db.turso_http import get_credentials, execute_many

    if not get_credentials():
        logger.warning("TURSO_DATA_URL / TURSO_DATA_TOKEN 미설정 — Turso 업로드 건너뜀")
        return

    now = datetime.utcnow().isoformat()
    today = now[:10]

    insert_sql = (
        "INSERT INTO watchlist_candidates "
        "(market, symbol, name, market_cap, sector, piotroski, "
        " debt_ratio, interest_coverage, cfo_positive_count, "
        " red_flags, regime_fit, roe, current_price, rel_3m, rel_6m, fit_score, data_notes, screened_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    history_insert_sql = (
        "INSERT OR REPLACE INTO watchlist_candidate_history "
        "(screened_date, market, symbol, name, sector, piotroski, regime_fit, current_price) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )

    BATCH = 50

    # 상위 N개만 유지하므로 매주 전체 교체 (DROP → CREATE → INSERT).
    # watchlist_candidate_history는 절대 DROP하지 않는다 — 성적표가 과거 스크리닝
    # 시점의 후보/가격을 계속 참조해야 하기 때문.
    init_statements = [
        ("DROP TABLE IF EXISTS watchlist_candidates", None),
        (CREATE_TABLE_SQL, None),
        (HISTORY_TABLE_SQL, None),
    ]

    for i in range(0, len(candidates), BATCH):
        chunk = candidates[i : i + BATCH]
        statements = list(init_statements) if i == 0 else []
        for c in chunk:
            statements.append((insert_sql, [
                c["market"],
                c["symbol"],
                c.get("name"),
                c.get("market_cap"),
                c.get("sector"),
                c.get("piotroski"),
                c.get("debt_ratio"),
                c.get("interest_coverage"),
                c.get("cfo_positive_count"),
                json.dumps(c.get("red_flags") or [], ensure_ascii=False),
                c.get("regime_fit"),
                c.get("roe"),
                c.get("current_price"),
                c.get("rel_3m"),
                c.get("rel_6m"),
                c.get("fit_score"),
                json.dumps(c.get("data_notes") or {}, ensure_ascii=False),
                now,
            ]))
            statements.append((history_insert_sql, [
                today,
                c["market"],
                c["symbol"],
                c.get("name"),
                c.get("sector"),
                c.get("piotroski"),
                c.get("regime_fit"),
                c.get("current_price"),
            ]))
        try:
            execute_many(statements, timeout=60)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            logger.error("Turso 업로드 실패 (HTTP %s): %s", e.code, detail)
            raise

        logger.info("Turso 업로드: %d/%d 완료", min(i + BATCH, len(candidates)), len(candidates))

    logger.info("Turso 업로드 완료: 총 %d 종목", len(candidates))


def send_telegram_warning(text: str) -> None:
    """SPEC §6.3 — 캐시 적중률 저하·회로차단기 작동 경고 발송. 미설정이면 조용히
    건너뛴다(다른 스크립트의 텔레그램 발송부와 동일 패턴)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.info("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 미설정 — 경고 발송 건너뜀")
        return

    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        logger.info("텔레그램 경고 발송 완료")
    except Exception as e:
        logger.error("텔레그램 경고 발송 실패: %s", e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["US", "KR", "ALL"], default="ALL")
    args = parser.parse_args()

    markets = ["US", "KR"] if args.market == "ALL" else [args.market]

    logger.info("=== 워치리스트 스크리닝 시작 (시장: %s, REFRESH_BUDGET=%d) ===", markets, REFRESH_BUDGET)

    # 1. 유니버스 수집 + 재무 데이터 (예산 내 종목만 라이브 갱신, 나머지는 캐시)
    universe, run_state = collect_universe(markets=markets, refresh_budget=REFRESH_BUDGET)

    if not universe:
        logger.error("유니버스 데이터 없음. 종료.")
        sys.exit(1)

    # 2. 함정 필터 적용 (순위 없음 — 통과한 종목 전부가 후보)
    passed, failed, insufficient = run_screen(universe)

    # 3. SQLite 저장 (로컬 백업)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        save_candidates(conn, passed)
        save_history(conn, passed, datetime.utcnow().strftime("%Y-%m-%d"))
    finally:
        conn.close()

    # 4. Turso 업로드 (프론트엔드용)
    push_to_turso(passed)

    # 5. 캐시 적중률 확인 — 낮거나 회로차단기가 작동했으면 텔레그램 경고만
    #    보내고 job은 그대로 성공 처리한다 (SPEC §6.3, job 실패 처리 안 함)
    attempted = run_state["live_ok"] + run_state["cache_fallback"] + run_state["no_data_at_all"]
    coverage_rate = (run_state["live_ok"] + run_state["cache_fallback"]) / attempted if attempted else 1.0
    if run_state["circuit_tripped"] or coverage_rate < CACHE_HIT_RATE_THRESHOLD:
        lines = [f"⚠️ <b>워치리스트 스크리닝 경고</b> ({datetime.utcnow().strftime('%Y-%m-%d')})"]
        if run_state["circuit_tripped"]:
            lines.append("야후 rate limit으로 회로차단기가 작동해 일부 종목을 캐시로 대체했습니다.")
        if coverage_rate < CACHE_HIT_RATE_THRESHOLD:
            lines.append(
                f"이번 주 갱신 대상 커버리지 {coverage_rate*100:.0f}% "
                f"(라이브 성공 {run_state['live_ok']} / 캐시 폴백 {run_state['cache_fallback']} / "
                f"완전 실패 {run_state['no_data_at_all']})"
            )
        logger.warning("캐시 적중률 낮음 또는 회로차단기 작동 — 텔레그램 경고 발송")
        send_telegram_warning("\n".join(lines))

    # 6. 결과 요약
    print("\n" + "=" * 60)
    print(f"  워치리스트 스크리닝 결과")
    print("=" * 60)
    print(f"  유니버스:      {len(universe):>4} 종목")
    print(f"  필터 통과:     {len(passed):>4} 종목 (= 최종 후보, 순위 없음)")
    print(f"  탈락:          {len(failed):>4} 종목 ({len(failed)/len(universe)*100:.1f}%)")
    print(f"  데이터부족:    {len(insufficient):>4} 종목 ({len(insufficient)/len(universe)*100:.1f}%)")

    for market in ("US", "KR"):
        group = [c for c in passed if c["market"] == market]
        if not group:
            continue
        print(f"\n  [{market}] 후보 {len(group)}종목: " + ", ".join(c["symbol"] for c in group))

    print("=" * 60)


if __name__ == "__main__":
    main()
