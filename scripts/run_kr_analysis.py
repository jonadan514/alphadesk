"""
한국 주식 통합 분석 파이프라인
Usage: python scripts/run_kr_analysis.py [--date YYYY-MM-DD]
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db, init_db


def _log(phase: str, msg: str, t0: float | None = None) -> None:
    elapsed = f"  [{time.time()-t0:.1f}s]" if t0 else ""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {phase}{elapsed}  {msg}")


# ── phases ─────────────────────────────────────────────────────────────────

def phase1_sector(t0: float) -> dict:
    _log("Phase1", "섹터 분석 시작")
    try:
        from src.analyzers.kr_sector_analyzer import analyze
        result = analyze()
        _log("Phase1", f"사이클={result['cycle_label']}", t0)
        return result
    except Exception as e:
        _log("Phase1", f"섹터 분석 실패: {e}")
        return {}


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="KR Stock Integrated Analysis")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                        help="분석 기준일 YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()
    analysis_date = args.date

    t0 = time.time()
    print("=" * 60)
    print(f"  KR Stock 통합 분석  |  date={analysis_date}")
    print("=" * 60)

    conn = get_db()
    init_db(conn)
    conn.close()

    # sector analyzer가 kr_sector_analysis 테이블에 스스로 저장한다
    phase1_sector(t0)

    # WAL → 메인 DB 체크포인트 (Next.js readonly 연결이 즉시 읽을 수 있도록)
    try:
        import sqlite3 as _sqlite3
        _conn = _sqlite3.connect(str(ROOT / "output" / "data.db"))
        _conn.execute("PRAGMA wal_checkpoint(FULL)")
        _conn.close()
        _log("Final", "WAL 체크포인트 완료")
    except Exception as e:
        print(f"[WAL 체크포인트 경고] {e}")

    elapsed = time.time() - t0
    print("=" * 60)
    print(f"  완료  |  총 소요: {elapsed:.1f}초")
    print("=" * 60)


if __name__ == "__main__":
    main()
