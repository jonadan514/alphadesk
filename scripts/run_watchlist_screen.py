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
  rel_3m              REAL,
  rel_6m              REAL,
  fit_score           REAL,
  screened_at         TEXT NOT NULL,
  UNIQUE(market, symbol)
)"""

# 매주 전체 교체 (상위 N개만 유지하므로 이전 회차 잔존 방지)
SCHEMA = f"""
DROP TABLE IF EXISTS watchlist_candidates;
{CREATE_TABLE_SQL};
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
            c.get("roe"),
            c.get("rel_3m"),
            c.get("rel_6m"),
            c.get("fit_score"),
            now,
        )
        for c in candidates
    ]
    conn.executemany(
        """
        INSERT INTO watchlist_candidates
          (market, symbol, name, market_cap, sector, piotroski,
           debt_ratio, interest_coverage, cfo_positive_count,
           red_flags, regime_fit, roe, rel_3m, rel_6m, fit_score, screened_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.commit()
    logger.info("DB 저장 완료: %d 종목", len(rows))


def _turso_val(v):
    """Python 값 → Turso Hrana v2 args 형식."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        import math
        if math.isnan(v) or math.isinf(v):
            return {"type": "null"}
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

    insert_sql = (
        "INSERT INTO watchlist_candidates "
        "(market, symbol, name, market_cap, sector, piotroski, "
        " debt_ratio, interest_coverage, cfo_positive_count, "
        " red_flags, regime_fit, roe, rel_3m, rel_6m, fit_score, screened_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    BATCH = 50
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 상위 N개만 유지하므로 매주 전체 교체 (DROP → CREATE → INSERT)
    init_requests = [
        {"type": "execute", "stmt": {"sql": "DROP TABLE IF EXISTS watchlist_candidates"}},
        {"type": "execute", "stmt": {"sql": CREATE_TABLE_SQL}},
    ]

    for i in range(0, len(candidates), BATCH):
        chunk = candidates[i : i + BATCH]
        requests_list = list(init_requests) if i == 0 else []
        for c in chunk:
            requests_list.append({
                "type": "execute",
                "stmt": {
                    "sql": insert_sql,
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
                        _turso_val(c.get("roe")),
                        _turso_val(c.get("rel_3m")),
                        _turso_val(c.get("rel_6m")),
                        _turso_val(c.get("fit_score")),
                        _turso_val(now),
                    ],
                },
            })
        body = json.dumps({"requests": requests_list}).encode()
        req = urllib.request.Request(
            f"{url}/v2/pipeline",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            logger.error("Turso 업로드 실패 (HTTP %s): %s", e.code, detail)
            raise

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

    # 2.5. 시장 적합 점수 → 시장별 상위 50개만 후보로
    from analyzers.market_fit_scorer import score_and_rank
    total_passed = len(passed)
    passed = score_and_rank(passed, top_n=50)

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
    print(f"  유니버스:      {len(universe):>4} 종목")
    print(f"  필터 통과:     {total_passed:>4} 종목")
    print(f"  탈락:          {len(failed):>4} 종목 ({len(failed)/len(universe)*100:.1f}%)")
    print(f"  최종 후보:     {len(passed):>4} 종목 (시장 적합 점수 시장별 상위 50)")

    for market in ("US", "KR"):
        group = [c for c in passed if c["market"] == market]
        if not group:
            continue
        print(f"\n  [{market}] 상위 10종목 (적합점수)")
        for c in group[:10]:
            print(f"    {c['symbol']:<8} {c.get('fit_score', 0):>5.1f}  {c.get('regime_fit','')}")

    print("=" * 60)


if __name__ == "__main__":
    main()
