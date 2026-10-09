"""종목 몇 개의 성장 판정 근거를 그대로 보여 준다(읽기 전용, 2026-10-09).

워치리스트 "성장/정체/역성장"(연간 매출 3년 CAGR)이 왜 그렇게 나왔는지 확인용:
연간 매출·영업이익(fundamentals_cache income), 계산된 3년 CAGR·1년 성장률·등급,
분기 매출·영업이익(income_quarterly), 저장된 watchlist_candidates 값.

    python scripts/inspect_company_growth.py --market KR --tickers 005930 000660
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from src.analyzers.company_growth import (REVENUE_KEYS, growth_tier, quarterly_margin_change,
                                          revenue_cagr, revenue_yoy)
from src.db.data_store import get_db
from src.db.fundamentals_cache import get_cached_financials_bulk
from compute_watchlist_valuation import income_periods


def _t(v) -> str:
    return "-" if v is None else f"{v / 1e12:,.2f}조" if abs(v) >= 1e11 else f"{v / 1e6:,.0f}M"


def _pct(v) -> str:
    return "-" if v is None else f"{v * 100:+.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["US", "KR"], required=True)
    ap.add_argument("--tickers", nargs="+", required=True)
    args = ap.parse_args()
    conn = get_db()
    cached = get_cached_financials_bulk(conn, args.tickers)
    for t in args.tickers:
        print(f"\n===== {args.market} {t} =====")
        c = cached.get(t)
        if not c:
            print("  캐시 없음")
            continue
        periods = sorted(income_periods(c.get("financials")), key=lambda p: p[0], reverse=True)
        print("  [연간] 회계기간      매출        영업이익")
        for end, d in periods:
            rev = next((d[k] for k in REVENUE_KEYS if d.get(k) is not None), None)
            print(f"         {end}  {_t(rev):>10}  {_t(d.get('Operating Income')):>10}")
        cagr, yoy = revenue_cagr(periods), revenue_yoy(periods)
        print(f"  -> 3년 CAGR {_pct(cagr)} / 최근 1년 {_pct(yoy)} / 등급 {growth_tier(cagr)}")
        q = c.get("financials_quarterly")
        if q is not None and not q.empty:
            print("  [분기] 분기말        매출        영업이익")
            for col in q.columns:
                s = q[col]
                rev = next((s[k] for k in REVENUE_KEYS if k in s.index and s[k] == s[k]), None)
                op = s["Operating Income"] if "Operating Income" in s.index and s["Operating Income"] == s["Operating Income"] else None
                print(f"         {col.strftime('%Y-%m-%d')}  {_t(rev):>10}  {_t(op):>10}")
            print(f"  -> 분기 이익률 {quarterly_margin_change(q)}")
        row = conn.execute(
            "SELECT revenue_cagr_3y, revenue_yoy, growth_tier, op_margin_q_status "
            "FROM watchlist_candidates WHERE market = ? AND symbol = ?", (args.market, t)).fetchall()
        print(f"  [watchlist_candidates 저장값] {row[0] if row else '후보 아님'}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
