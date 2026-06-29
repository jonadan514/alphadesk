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
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from collectors.watchlist_collector import collect_universe
from analyzers.trap_filter import run_screen

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = ROOT / "output" / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist_candidates (
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
  screened_at         TEXT NOT NULL,
  UNIQUE(market, symbol)
);
CREATE INDEX IF NOT EXISTS idx_wl_market ON watchlist_candidates(market);
CREATE INDEX IF NOT EXISTS idx_wl_regime ON watchlist_candidates(regime_fit);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
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
            now,
        )
        for c in candidates
    ]
    conn.executemany(
        """
        INSERT INTO watchlist_candidates
          (market, symbol, name, market_cap, sector, piotroski,
           debt_ratio, interest_coverage, cfo_positive_count,
           red_flags, regime_fit, screened_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(market, symbol) DO UPDATE SET
          name=excluded.name, market_cap=excluded.market_cap,
          sector=excluded.sector, piotroski=excluded.piotroski,
          debt_ratio=excluded.debt_ratio,
          interest_coverage=excluded.interest_coverage,
          cfo_positive_count=excluded.cfo_positive_count,
          red_flags=excluded.red_flags,
          regime_fit=excluded.regime_fit,
          screened_at=excluded.screened_at
        """,
        rows,
    )
    conn.commit()
    logger.info("DB 저장 완료: %d 종목", len(rows))


def _turso_val(v):
    """Python 값 → Turso HTTP API args 형식."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": int(v)}
    if isinstance(v, int):
        return {"type": "integer", "value": v}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


def push_to_turso(candidates: list[dict]) -> None:
    """스크리닝 결과를 Turso에 upsert."""
    import urllib.request

    url = os.environ.get("TURSO_DATA_URL", "").replace("libsql://", "https://")
    token = os.environ.get("TURSO_DATA_TOKEN", "")
    if not url or not token:
        logger.warning("TURSO_DATA_URL / TURSO_DATA_TOKEN 미설정 — Turso 업로드 건너뜀")
        return

    now = datetime.utcnow().isoformat()

    create_stmt = {
        "type": "execute",
        "stmt": {
            "sql": (
                "CREATE TABLE IF NOT EXISTS watchlist_candidates ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  market TEXT NOT NULL,"
                "  symbol TEXT NOT NULL,"
                "  name TEXT,"
                "  market_cap REAL,"
                "  sector TEXT,"
                "  piotroski INTEGER,"
                "  debt_ratio REAL,"
                "  interest_coverage REAL,"
                "  cfo_positive_count INTEGER,"
                "  red_flags TEXT,"
                "  regime_fit TEXT,"
                "  screened_at TEXT NOT NULL,"
                "  UNIQUE(market, symbol)"
                ")"
            )
        },
    }

    upsert_sql = (
        "INSERT INTO watchlist_candidates "
        "(market, symbol, name, market_cap, sector, piotroski, "
        " debt_ratio, interest_coverage, cfo_positive_count, "
        " red_flags, regime_fit, screened_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(market, symbol) DO UPDATE SET "
        "name=excluded.name, market_cap=excluded.market_cap, "
        "sector=excluded.sector, piotroski=excluded.piotroski, "
        "debt_ratio=excluded.debt_ratio, "
        "interest_coverage=excluded.interest_coverage, "
        "cfo_positive_count=excluded.cfo_positive_count, "
        "red_flags=excluded.red_flags, "
        "regime_fit=excluded.regime_fit, "
        "screened_at=excluded.screened_at"
    )

    BATCH = 50
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for i in range(0, len(candidates), BATCH):
        chunk = candidates[i : i + BATCH]
        requests_list = [create_stmt]
        for c in chunk:
            requests_list.append({
                "type": "execute",
                "stmt": {
                    "sql": upsert_sql,
                    "args": [
                        _turso_val(c["market"]),
                        _turso_val(c["symbol"]),
                        _turso_val(c.get("name")),
                        _turso_val(c.get("market_cap")),
                        _turso_val(c.get("sector")),
                        _turso_val(c.get("piotroski")),
                        _turso_val(c.get("debt_ratio")),
                        _turso_val(c.get("interest_coverage")),
                        _turso_val(c.get("cfo_positive_count")),
                        _turso_val(json.dumps(c.get("red_flags") or [], ensure_ascii=False)),
                        _turso_val(c.get("regime_fit")),
                        _turso_val(now),
                    ],
                },
            })
        requests_list.append({"type": "close"})

        body = json.dumps({"requests": requests_list}).encode()
        req = urllib.request.Request(
            f"{url}/v2/pipeline",
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()

        logger.info("Turso 업로드: %d/%d 완료", min(i + BATCH, len(candidates)), len(candidates))

    logger.info("Turso 업로드 완료: 총 %d 종목", len(candidates))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["US", "KR", "ALL"], default="ALL")
    args = parser.parse_args()

    markets = ["US", "KR"] if args.market == "ALL" else [args.market]

    logger.info("=== 워치리스트 스크리닝 시작 (시장: %s) ===", markets)

    # 1. 유니버스 수집 + 재무 데이터
    universe = collect_universe(markets=markets)

    if not universe:
        logger.error("유니버스 데이터 없음. 종료.")
        sys.exit(1)

    # 2. 함정 필터 적용
    passed, failed = run_screen(universe)

    # 3. SQLite 저장 (로컬 백업)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        save_candidates(conn, passed)
    finally:
        conn.close()

    # 4. Turso 업로드 (프론트엔드용)
    push_to_turso(passed)

    # 4. 결과 요약
    print("\n" + "=" * 60)
    print(f"  워치리스트 스크리닝 결과")
    print("=" * 60)
    print(f"  유니버스:  {len(universe):>4} 종목")
    print(f"  통과:      {len(passed):>4} 종목")
    print(f"  탈락:      {len(failed):>4} 종목")
    print(f"  탈락률:    {len(failed)/len(universe)*100:.1f}%")

    by_regime = {}
    for c in passed:
        by_regime.setdefault(c["regime_fit"], []).append(c["symbol"])
    for regime, syms in by_regime.items():
        print(f"\n  [{regime.upper()}] {len(syms)}종목")
        for s in syms[:10]:
            print(f"    {s}")
        if len(syms) > 10:
            print(f"    ... 외 {len(syms)-10}종목")

    print("=" * 60)


if __name__ == "__main__":
    main()
