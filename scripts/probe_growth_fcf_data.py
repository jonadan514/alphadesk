"""성장률·FCF Yield를 만들 데이터가 실제로 있는지 실측한다. 아무것도 쓰지 않는다.

배경:
MASTER_PLAN_research_radar.md Phase C에 "밸류에이션 컬럼(FCF Yield, PER)",
"성장 컬럼(매출 3년 CAGR + 최근 1년 + 영업이익 방향)", "섹터 중앙값 계산기"가
적혀 있다. PER은 2026-09-24에 워치리스트·분기 화면 양쪽에 들어갔고, 나머지는
아직이다.

그런데 Phase C는 분기 재설계 이전에 쓰인 문서라 "데이터가 있다"는 전제가
확인된 적이 없다. 지난번 테마 그룹화 제안이 실측(커버리지 25%/43%)으로
뒤집힌 적이 있어서, 설계 전에 먼저 잰다.

재는 것 (KR/US 따로 - yfinance의 한국 커버리지가 미국보다 나쁠 수 있다):

  1. 연차 손익계산서가 종목당 몇 개 회계연도나 있는가
     -> 3년 CAGR은 최소 4개 연도 시점이 필요하다(4점 = 3구간).
  2. 매출 계정 이름이 무엇으로 들어오는가
     -> yfinance 라벨이 시장마다 다르면 키를 하드코딩할 수 없다.
  3. 현금흐름표에 FCF를 만들 재료가 있는가
     -> "Free Cash Flow"가 직접 있는지, 없으면 영업현금흐름 - 자본지출로
        만들 수 있는지.
  4. quarterly_financials_raw가 몇 년치나 있는가
     -> 한국은 yfinance 대신 DART 분기를 합쳐 연매출을 만들 수 있을지 판단용.

Usage (격리 필요 없음 - pykrx를 쓰지 않는다):
    python scripts/probe_growth_fcf_data.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db

# 3년 CAGR에 필요한 연도 시점 수. 4개 시점 = 3개 구간.
YEARS_FOR_3Y_CAGR = 4


def _log(msg: str) -> None:
    print(f"[probe-growth] {msg}", flush=True)


def _pct(n: int, d: int) -> str:
    return f"{n/d*100:.0f}%" if d else "-"


def load_candidates(conn) -> dict[str, list[str]]:
    rows = conn.execute("SELECT market, symbol FROM watchlist_candidates").fetchall()
    out: dict[str, list[str]] = {}
    for market, symbol in rows:
        out.setdefault(market, []).append(symbol)
    return out


def probe_statement(conn, market: str, tickers: list[str], statement: str) -> dict:
    """fundamentals_cache에서 해당 재무제표의 회계기간 수와 계정 이름을 센다."""
    periods: dict[str, set[str]] = {}
    key_counter: Counter[str] = Counter()
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT ticker, period_end, data FROM fundamentals_cache "
        f"WHERE statement = ? AND ticker IN ({placeholders})",
        (statement, *tickers),
    ).fetchall()
    for ticker, period_end, data in rows:
        periods.setdefault(ticker, set()).add(str(period_end))
        try:
            for k in json.loads(data).keys():
                key_counter[k] += 1
        except Exception:
            pass
    return {"periods": periods, "keys": key_counter, "rows": len(rows)}


def report_periods(market: str, statement: str, tickers: list[str], periods: dict[str, set[str]]) -> None:
    n = len(tickers)
    have = len(periods)
    counts = Counter(len(v) for v in periods.values())
    _log(f"  [{statement}] 보유 종목 {have}/{n} ({_pct(have, n)})")
    if counts:
        dist = " / ".join(f"{k}개년 {v}종목" for k, v in sorted(counts.items()))
        _log(f"    회계기간 분포: {dist}")
        enough = sum(v for k, v in counts.items() if k >= YEARS_FOR_3Y_CAGR)
        _log(f"    3년 CAGR 가능({YEARS_FOR_3Y_CAGR}개년 이상): {enough}/{n} ({_pct(enough, n)})")


def report_keys(label: str, keys: Counter, top: int = 18) -> None:
    _log(f"    {label} 계정 상위 {top}:")
    for k, v in keys.most_common(top):
        _log(f"      {v:>5}회  {k}")


def probe_fcf_parts(keys: Counter) -> None:
    """FCF를 만들 재료가 있는지 - 직접 항목이 있으면 제일 좋고, 없으면 두 항목의 차."""
    direct = [k for k in keys if "free cash flow" in k.lower()]
    cfo = [k for k in keys if "operating cash flow" in k.lower()
           or "cash flow from continuing operating" in k.lower()]
    capex = [k for k in keys if "capital expenditure" in k.lower()]
    _log(f"    FCF 직접 항목: {direct or '없음'}")
    _log(f"    영업현금흐름 항목: {cfo or '없음'}")
    _log(f"    자본지출 항목:   {capex or '없음'}")


def probe_quarterly_years(conn, market: str, tickers: list[str]) -> None:
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT ticker, fiscal_year FROM quarterly_financials_raw "
        f"WHERE market = ? AND ticker IN ({placeholders})",
        (market, *tickers),
    ).fetchall()
    years: dict[str, set[int]] = {}
    for ticker, fy in rows:
        years.setdefault(ticker, set()).add(int(fy))   # Turso가 INTEGER를 문자열로 준다
    counts = Counter(len(v) for v in years.values())
    n = len(tickers)
    _log(f"  [quarterly_financials_raw] 보유 종목 {len(years)}/{n} ({_pct(len(years), n)})")
    if counts:
        dist = " / ".join(f"{k}개 연도 {v}종목" for k, v in sorted(counts.items()))
        _log(f"    연도 수 분포: {dist}")
        all_years: Counter[int] = Counter()
        for s in years.values():
            for y in s:
                all_years[y] += 1
        _log("    연도별 보유 종목 수: "
             + " / ".join(f"{y} {c}" for y, c in sorted(all_years.items())))


def main() -> int:
    conn = get_db()
    by_market = load_candidates(conn)
    if not by_market:
        _log("워치리스트 후보가 없다 - 중단")
        return 1

    for market in sorted(by_market):
        tickers = by_market[market]
        _log("=" * 64)
        _log(f"[{market}] 워치리스트 후보 {len(tickers)}종목 기준")

        inc = probe_statement(conn, market, tickers, "income")
        report_periods(market, "income(연차 손익)", tickers, inc["periods"])
        report_keys("손익", inc["keys"])

        cf = probe_statement(conn, market, tickers, "cashflow")
        report_periods(market, "cashflow(연차 현금흐름)", tickers, cf["periods"])
        probe_fcf_parts(cf["keys"])

        probe_quarterly_years(conn, market, tickers)

    conn.close()
    _log("=" * 64)
    _log("완료 - 아무것도 쓰지 않았다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
