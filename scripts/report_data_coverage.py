"""저장만 하고 안 쓰는 자료의 채움률 점검 (읽기 전용, 2026-10-05).

1) fetch_status.info_payload(yfinance 기업 정보 전체) - 후보 항목별 미국/한국 값 있는 종목 수, 수집 시점
2) fundamentals_cache 분기 손익(income_quarterly) - 이익률 계산에 필요한 줄(매출총이익·영업이익)이 있는 종목·분기 수
3) earnings_surprise - 시장별 종목 수, 최근 발표일 분포

    python scripts/report_data_coverage.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db

INFO_KEYS = [
    # 애널리스트·기대
    "numberOfAnalystOpinions", "targetMeanPrice", "recommendationMean", "recommendationKey",
    "forwardEps", "trailingEps", "forwardPE", "earningsQuarterlyGrowth", "earningsGrowth", "revenueGrowth",
    # 이익률·현금
    "grossMargins", "operatingMargins", "profitMargins", "freeCashflow", "returnOnEquity",
    # 가격 위치·위험
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "52WeekChange", "beta",
    # 보유·공매도
    "heldPercentInsiders", "heldPercentInstitutions", "shortPercentOfFloat", "shortRatio",
    # 기타
    "dividendYield", "fullTimeEmployees", "currentPrice",
]
QUARTER_LINES = ["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "Cost Of Revenue", "EBITDA"]


def _filled(v) -> bool:
    return v not in (None, "", "None", "NaN", "nan") and not (isinstance(v, float) and v != v)


def main() -> int:
    conn = get_db()

    print("== 1. yfinance 기업 정보 (fetch_status.info_payload) ==")
    tickers = conn.execute("SELECT ticker, market FROM fetch_status WHERE info_payload IS NOT NULL").fetchall()
    total = Counter(m for _, m in tickers)
    filled: dict[str, Counter] = defaultdict(Counter)
    samples: dict[str, dict] = defaultdict(dict)
    all_keys: Counter = Counter()
    fresh: Counter = Counter()
    batch = [t for t, _ in tickers]
    for i in range(0, len(batch), 100):
        chunk = batch[i:i + 100]
        rows = conn.execute(
            f"SELECT ticker, market, info_payload, last_success_at FROM fetch_status WHERE ticker IN ({','.join('?' * len(chunk))})",
            tuple(chunk)).fetchall()
        for ticker, market, payload, last in rows:
            try:
                info = json.loads(payload)
            except Exception:
                continue
            fresh[(market, (last or "")[:7])] += 1
            for k, v in info.items():
                if _filled(v):
                    all_keys[k] += 1
            for k in INFO_KEYS:
                if _filled(info.get(k)):
                    filled[market][k] += 1
                    samples[market].setdefault(k, (ticker, info.get(k)))
    print(f"  종목 수: " + ", ".join(f"{m} {n}" for m, n in total.items()))
    print(f"  마지막 성공 수집 월: " + ", ".join(f"{m} {mon}:{n}" for (m, mon), n in sorted(fresh.items())))
    print(f"  {'항목':28s} {'미국':>12s} {'한국':>12s}   예시")
    for k in INFO_KEYS:
        us, kr = filled["US"][k], filled["KR"][k]
        ex = samples["US"].get(k) or samples["KR"].get(k)
        print(f"  {k:28s} {us:5d}/{total['US']:<5d} {kr:5d}/{total['KR']:<5d}   {ex}")
    print(f"  (참고) 전체 항목 수 {len(all_keys)}, 값이 가장 많이 찬 항목 30개: "
          + ", ".join(f"{k}:{n}" for k, n in all_keys.most_common(30)))

    print("== 2. 분기 손익 (fundamentals_cache, income_quarterly) ==")
    rows = conn.execute(
        "SELECT market, ticker, " + ", ".join(f"json_extract(data, '$.\"{l}\"')" for l in QUARTER_LINES)
        + " FROM fundamentals_cache WHERE statement = 'income_quarterly'").fetchall()
    per_ticker: dict[tuple, Counter] = defaultdict(Counter)
    for r in rows:
        key = (r[0], r[1])
        per_ticker[key]["_q"] += 1
        for l, v in zip(QUARTER_LINES, r[2:]):
            if _filled(v):
                per_ticker[key][l] += 1
    by_market: dict[str, Counter] = defaultdict(Counter)
    for (m, _t), c in per_ticker.items():
        by_market[m]["종목"] += 1
        for l in QUARTER_LINES:
            if c[l] >= 5:          # 전년동기 비교에 5개 분기 필요
                by_market[m][l] += 1
    for m, c in by_market.items():
        print(f"  {m}: 분기 손익 있는 종목 {c['종목']} - 5개 분기 이상 값 있는 종목: "
              + ", ".join(f"{l} {c[l]}" for l in QUARTER_LINES))

    print("== 3. 실적 서프라이즈 (earnings_surprise) ==")
    rows = conn.execute("SELECT market, substr(report_date, 1, 7), COUNT(*), "
                        "SUM(CASE WHEN surprise_pct IS NOT NULL THEN 1 ELSE 0 END) "
                        "FROM earnings_surprise GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
    for m, mon, n, s in rows:
        print(f"  {m} {mon}: {n}종목 (서프라이즈 값 {s})")
    print("== 4. 분기 영업이익률 전년동기 비교 (2026-10-05 추가) ==")
    for label, sql in [
        ("테마 소속 기업(theme_member_signals, 최신 주)",
         "SELECT market, om_status, COUNT(*) FROM theme_member_signals "
         "WHERE week_start = (SELECT MAX(week_start) FROM theme_member_signals) GROUP BY 1, 2 ORDER BY 1, 2"),
        ("워치리스트 후보(watchlist_candidates)",
         "SELECT market, op_margin_q_status, COUNT(*) FROM watchlist_candidates GROUP BY 1, 2 ORDER BY 1, 2"),
    ]:
        try:
            rows = conn.execute(sql).fetchall()
            print(f"  {label}: " + ", ".join(f"{m} {st or '데이터부족'} {n}" for m, st, n in rows))
        except Exception as e:
            print(f"  {label}: 조회 실패 {e}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
