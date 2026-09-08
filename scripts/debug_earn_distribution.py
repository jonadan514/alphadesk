"""실적 축이 전부 up2로 쏠리는 원인 진단 (읽기 전용) - 확인 후 삭제.

SPEC §8("임계값은 임의값, 첫 몇 주 실데이터로 조정")의 실데이터 근거를 만든다.
현재 판정: 기업별로 최근 분기 매출 YoY 성장률 > 0 이면 improved,
테마 단위로 improved 비율이 0.70 이상이면 up2.

기준값은 건드리지 않고, 기업별 YoY 성장률 분포와 임계값 시뮬레이션만 뽑는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.fundamentals_cache import get_cached_financials_bulk
from src.db.theme_signals import get_approved_theme_members
import yaml

THEMES_YAML = ROOT / "config" / "themes.yaml"
MIN_QUARTERS = 5


def main() -> None:
    conn = get_db()
    with open(THEMES_YAML, encoding="utf-8") as f:
        themes = [t for t in yaml.safe_load(f)["themes"] if t.get("status") == "active"]

    growths = {"US": [], "KR": []}
    quarters_avail = {"US": [], "KR": []}
    seen = {"US": set(), "KR": set()}

    for market in ("US", "KR"):
        tickers = set()
        for th in themes:
            if market not in th.get("markets", []):
                continue
            for m in get_approved_theme_members(conn, th["id"], market, ("direct", "partial")):
                tickers.add(m["ticker"])
        cache = get_cached_financials_bulk(conn, sorted(tickers))
        for tk, data in cache.items():
            if data is None:
                continue
            q = data.get("financials_quarterly")
            if q is None or q.empty or "Total Revenue" not in q.index:
                continue
            rev = q.loc["Total Revenue"].dropna()
            quarters_avail[market].append(len(rev))
            if len(rev) < MIN_QUARTERS:
                continue
            try:
                cur, prior = float(rev.iloc[0]), float(rev.iloc[4])
            except Exception:
                continue
            if not prior:
                continue
            if tk in seen[market]:
                continue
            seen[market].add(tk)
            growths[market].append((tk, (cur / prior - 1) * 100))

    def pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        return round(s[min(int(len(s) * p / 100), len(s) - 1)], 1)

    for market in ("US", "KR"):
        g = [v for _, v in growths[market]]
        qa = quarters_avail[market]
        print(f"=== {market}: 기업 {len(g)}개 (분기수 중앙값 {pct(qa,50)}) ===")
        if not g:
            print("  데이터 없음\n")
            continue
        print(f"  YoY 매출성장률(%): 10%={pct(g,10)} 25%={pct(g,25)} 중앙값={pct(g,50)} "
              f"75%={pct(g,75)} 90%={pct(g,90)}")
        for thr in (0, 3, 5, 10, 15, 20):
            n = sum(1 for v in g if v > thr)
            print(f"    성장률 > {thr:2d}% 인 기업: {n}/{len(g)} ({n/len(g)*100:.0f}%)")
        print(f"  역성장(<0%) 기업: {sum(1 for v in g if v < 0)}/{len(g)}")
        print()

    # 현재 기준(>0%)이 왜 무의미한지: 테마별 improved 비율 분포
    print("=== 현재 기준(YoY>0)에서 테마별 improved 비율이 어떻게 나오는지 ===")
    for market in ("US", "KR"):
        by_ticker = dict(growths[market])
        ratios = []
        for th in themes:
            if market not in th.get("markets", []):
                continue
            ms = get_approved_theme_members(conn, th["id"], market, ("direct", "partial"))
            vals = [by_ticker[m["ticker"]] for m in ms if m["ticker"] in by_ticker]
            if len(vals) < 5:
                continue
            r0 = sum(1 for v in vals if v > 0) / len(vals)
            r5 = sum(1 for v in vals if v > 5) / len(vals)
            r10 = sum(1 for v in vals if v > 10) / len(vals)
            ratios.append((th["id"], len(vals), r0, r5, r10))
        print(f"  [{market}] 표본 5개 이상 테마 {len(ratios)}개")
        print(f"    {'테마':26s} n  >0%   >5%   >10%")
        for tid, n, r0, r5, r10 in sorted(ratios, key=lambda x: -x[2]):
            print(f"    {tid:26s} {n:2d} {r0:.2f}  {r5:.2f}  {r10:.2f}")
        print()

    conn.close()


if __name__ == "__main__":
    main()
