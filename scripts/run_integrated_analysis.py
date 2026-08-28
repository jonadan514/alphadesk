"""
통합 분석 파이프라인
Usage: python scripts/run_integrated_analysis.py [--date YYYY-MM-DD]
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.collectors.fetch_sp500_list import save_sp500_list
from src.collectors.fetch_sp500_prices import fetch_sp500_prices
from src.db.data_store import get_db, init_db, upsert_costs
from src.analyzers.sector_analyzer import analyze as analyze_sectors

SP500_CSV    = ROOT / "data" / "sp500_list.csv"
PRICES_CSV   = ROOT / "data" / "us_daily_prices.csv"

# ── helpers ────────────────────────────────────────────────────────────────

def _mtime_days(path: Path) -> float:
    if not path.exists():
        return float("inf")
    return (time.time() - path.stat().st_mtime) / 86400


def _log(phase: str, msg: str, t0: float | None = None) -> None:
    elapsed = f"  [{time.time()-t0:.1f}s]" if t0 else ""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {phase}{elapsed}  {msg}")


# ── phases ─────────────────────────────────────────────────────────────────

def phase0_refresh_data(t0: float) -> tuple:
    _log("Phase0", "데이터 신선도 체크")

    if _mtime_days(SP500_CSV) > 7:
        _log("Phase0", "sp500_list.csv 재수집 중…")
        sp500_df = save_sp500_list()
    else:
        import pandas as pd
        sp500_df = pd.read_csv(SP500_CSV)
        _log("Phase0", f"sp500_list.csv 캐시 사용 ({len(sp500_df)}종목)", t0)

    if _mtime_days(PRICES_CSV) > 1:
        _log("Phase0", "가격 데이터 재다운로드 중 (시간 소요)…")
        prices_df = fetch_sp500_prices()
    else:
        import pandas as pd
        prices_df = pd.read_csv(PRICES_CSV)
        _log("Phase0", f"prices 캐시 사용 ({len(prices_df):,}행)", t0)

    # symbol → DataFrame 매핑
    price_map: dict = {}
    if not prices_df.empty and "Symbol" in prices_df.columns:
        import pandas as pd
        prices_df["Date"] = pd.to_datetime(prices_df["Date"])
        for sym, grp in prices_df.groupby("Symbol"):
            price_map[sym] = grp.set_index("Date").sort_index()

    return sp500_df, price_map


def phase_costs(analysis_date: str, t0: float) -> None:
    _log("Phase1", "Costs 집계 시작")

    # gpt-4o-mini: $0.15/M input tokens, $0.60/M output tokens
    # 토큰 수는 API 응답의 usage를 기록하는 usage_tracker 싱글턴에서 읽는다
    from src.analyzers.ai_summary_generator import usage_tracker
    PRICE_IN  = 0.15 / 1_000_000
    PRICE_OUT = 0.60 / 1_000_000
    total_in  = usage_tracker.total_input_tokens
    total_out = usage_tracker.total_output_tokens
    cost_usd = round(total_in * PRICE_IN + total_out * PRICE_OUT, 6)

    entry = {
        "date":       analysis_date,
        "service":    "OpenAI",
        "model":      "gpt-4o-mini",
        "tokens_in":  total_in,
        "tokens_out": total_out,
        "cost_usd":   cost_usd,
        "note":       "daily pipeline (종목별 AI 요약은 주간 워치리스트에서 별도 집계)",
    }
    costs_data = {"entries": [entry]}
    _log("Phase1", f"Costs: in={total_in} out={total_out} cost=${cost_usd:.4f}", t0)

    conn = get_db()
    init_db(conn)
    upsert_costs(conn, costs_data)
    conn.close()
    _log("Phase1", "Costs DB upsert 완료", t0)


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="US Stock Integrated Analysis")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                        help="분석 기준일 YYYY-MM-DD (기본: 오늘)")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 60)
    print(f"  US Stock 통합 분석  |  date={args.date}")
    print("=" * 60)

    phase0_refresh_data(t0)
    phase_costs(args.date, t0)

    # ── Phase2 섹터 분석 ────────────────────────────────────────────────
    _log("Phase2", "섹터 분석 시작")
    try:
        analyze_sectors()
        _log("Phase2", "섹터 분석 저장 완료", t0)
    except Exception as e:
        print(f"[Phase2 경고] 섹터 분석 실패: {e}")

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
