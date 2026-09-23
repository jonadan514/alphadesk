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
# 워크플로가 빈 문자열을 넘길 수 있어(수동 실행 입력 미기입) or로 폴백한다 -
# os.getenv의 기본값은 "미설정"일 때만 쓰여서 빈 문자열이면 int("")로 죽는다.
# 250 근거(2026-09-14 실측): 유니버스가 KR 487 + US 503 = 990종목이 되면서
# 60으로는 전체를 한 바퀴 도는 데 17주가 걸린다. 종목당 라이브 갱신이 약 9초라
# 250이면 15-37분이고(잡 타임아웃 90분), 4주면 전체를 커버한다.
REFRESH_BUDGET = int(os.getenv("REFRESH_BUDGET") or "250")

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

# 매주 교체하되 시장 단위로만 지운다(아래 ensure_schema 참고) — DROP TABLE로
# 통째로 날리면 한쪽 시장만 돌렸을 때 다른 시장 후보가 조용히 사라진다.
SCHEMA = f"""
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


# 스크리닝 3분류(통과/탈락/데이터부족)를 전부 남기는 테이블.
#
# watchlist_candidates는 "통과 종목"만 담는 목록이라, 화면에서 어떤 종목이
# 안 보일 때 그게 탈락인지·데이터부족인지·아예 스크리닝 대상이 아닌지
# 구분할 수 없었다(테마 레이더의 재무 배지가 전부 "미확인"으로 뜨던 이유).
# 여기에 세 분류를 사유와 함께 남겨 그 구분을 가능하게 한다.
#
# candidates에 탈락 행을 섞지 않고 별도 테이블로 둔 이유: candidates를 읽는
# 곳이 워치리스트 화면·레이더 배지·섹터 분석·주간 브리핑 4곳이라, 그중
# 하나라도 status 필터를 빠뜨리면 탈락 종목이 후보처럼 보이게 된다.
SCREENING_RESULTS_SQL = """CREATE TABLE IF NOT EXISTS watchlist_screening_results (
  market      TEXT NOT NULL,
  symbol      TEXT NOT NULL,
  status      TEXT NOT NULL,
  red_flags   TEXT,
  piotroski   INTEGER,
  roe         REAL,
  screened_at TEXT NOT NULL,
  PRIMARY KEY (market, symbol)
)"""


def ensure_schema(conn: sqlite3.Connection, markets: list[str] | None = None) -> None:
    """테이블을 만들고, 이번에 스크리닝하는 시장의 기존 행만 비운다.
    markets가 None이면 아무것도 지우지 않는다(스키마만 보장)."""
    conn.executescript(SCHEMA)
    conn.execute(HISTORY_TABLE_SQL)
    conn.execute(SCREENING_RESULTS_SQL)
    for mkt in markets or []:
        conn.execute("DELETE FROM watchlist_candidates WHERE market = ?", (mkt,))
        conn.execute("DELETE FROM watchlist_screening_results WHERE market = ?", (mkt,))
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


def push_to_turso(candidates: list[dict], screening_rows: list[tuple[str, dict]] | None = None) -> None:
    """스크리닝 결과를 Turso에 upsert.
    screening_rows: (status, entry) 튜플 목록 - 통과/탈락/데이터부족 전부."""
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

    # 매주 전체 교체하되, **이번에 스크리닝한 시장만** 지운다.
    #
    # 예전엔 DROP TABLE로 통째로 날렸는데, 그러면 `--market KR`처럼 한쪽만
    # 돌렸을 때 다른 시장 후보가 조용히 전멸한다(2026-09-07에 실제로 미국
    # 149종목이 사라짐 - 전체 점검에서 "워치리스트 US 0개"로 발견). 테이블을
    # 지우는 대신 해당 시장 행만 DELETE한다.
    #
    # watchlist_candidate_history는 어느 경우에도 건드리지 않는다 — 성적표가
    # 과거 스크리닝 시점의 후보/가격을 계속 참조해야 하기 때문.
    screened_markets = sorted({c["market"] for c in candidates})
    init_statements = [
        (CREATE_TABLE_SQL, None),
        (HISTORY_TABLE_SQL, None),
        (SCREENING_RESULTS_SQL, None),
    ]
    for mkt in screened_markets:
        init_statements.append(("DELETE FROM watchlist_candidates WHERE market = ?", [mkt]))
        init_statements.append(("DELETE FROM watchlist_screening_results WHERE market = ?", [mkt]))
    logger.info("Turso 교체 대상 시장: %s (다른 시장 후보는 유지)", screened_markets)

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

    # 스크리닝 3분류 결과(통과/탈락/데이터부족)를 별도 테이블에 저장.
    # 후보 목록과 달리 여기엔 탈락·데이터부족도 사유와 함께 남는다.
    if screening_rows:
        sr_sql = (
            "INSERT OR REPLACE INTO watchlist_screening_results "
            "(market, symbol, status, red_flags, piotroski, roe, screened_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        for i in range(0, len(screening_rows), BATCH):
            chunk = screening_rows[i : i + BATCH]
            stmts = [(sr_sql, [
                e.get("market"), e.get("symbol"), status,
                json.dumps(e.get("red_flags") or [], ensure_ascii=False),
                e.get("piotroski"), e.get("roe"), now,
            ]) for status, e in chunk]
            try:
                execute_many(stmts, timeout=60)
            except urllib.error.HTTPError as e:
                logger.error("스크리닝 결과 업로드 실패 (HTTP %s): %s", e.code,
                             e.read().decode(errors="replace"))
                raise
        logger.info("스크리닝 결과 업로드 완료: %d행", len(screening_rows))


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
        ensure_schema(conn, markets)
        save_candidates(conn, passed)
        save_history(conn, passed, datetime.utcnow().strftime("%Y-%m-%d"))
    finally:
        conn.close()

    # 4. Turso 업로드 (프론트엔드용)
    screening_rows = (
        [("pass", e) for e in passed]
        + [("fail", e) for e in failed]
        + [("insufficient", e) for e in insufficient]
    )
    push_to_turso(passed, screening_rows)

    # 4-1. 밸류 지표(PSR/PER) 채우기
    #
    # 위 업로드가 이 시장 행을 DELETE 후 새로 INSERT하므로 지난주에 채운 psr/per/
    # valuation_tier는 방금 사라졌다. 업로드 **직후** 다시 계산해 넣어야 한다.
    #
    # 밸류는 부가 정보라 여기서 실패해도 스크리닝 자체는 성공으로 둔다 - 후보 목록은
    # 이미 올라갔고, 분기 재무(quarterly_financials_raw)가 아직 없는 시장이면 값만
    # 비는 게 맞다.
    try:
        from compute_watchlist_valuation import ensure_columns, run as fill_valuation
        from db.data_store import get_db

        vconn = get_db()
        try:
            ensure_columns(vconn)
            fill_valuation(vconn, markets)
        finally:
            vconn.close()
    except Exception as e:
        logger.warning("밸류 지표 계산 실패 — 후보 목록은 정상 업로드됨: %s", e)

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
