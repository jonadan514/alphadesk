"""한국 유니버스 트랩 필터 탈락 사유 분포 진단 (읽기 전용) - 확인 후 삭제.

MASTER_PLAN_research_radar.md §8의 열린 항목("한국 ROE 기준을 미국 12% 그대로
쓸지 - 데이터 확보 후 결정")을 판단하기 위한 자료. 기준값은 건드리지 않고,
캐시된 재무 데이터로 현재 기준을 그대로 적용했을 때 무엇이 몇 개를 걸러내는지만
집계한다.
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.fundamentals_cache import get_cached_financials_bulk
from src.collectors.kr_kospi_list import KOSPI_STOCKS
from analyzers.trap_filter import apply_trap_filters


def _cat(flag: str) -> str:
    """red_flag 문자열을 기준 종류로 묶는다."""
    if flag.startswith("Piotroski"):
        return "Piotroski <6"
    if flag.startswith("ROE"):
        return "ROE <12%"
    if flag.startswith("부채비율"):
        return "부채비율 >150%"
    if flag.startswith("이자보상"):
        return "이자보상 <3배"
    if "현금흐름" in flag:
        return "영업현금흐름"
    if "감소" in flag:
        return "매출/순이익 감소"
    return flag[:20]


def main() -> None:
    conn = get_db()
    names = {c: n for c, n, _ in KOSPI_STOCKS}
    codes = sorted(names)

    cache = get_cached_financials_bulk(conn, codes)
    fs_rows = conn.execute(
        "SELECT ticker, info_payload FROM fetch_status WHERE market = 'KR'"
    ).fetchall()
    import json
    info_by = {}
    for t, payload in fs_rows:
        try:
            info_by[t] = json.loads(payload) if payload else {}
        except Exception:
            info_by[t] = {}

    total = passed = insufficient = 0
    flag_counter = Counter()
    sole_reason = Counter()   # 이 기준 하나만 걸린 종목 수 = "이것만 완화하면 통과"
    roe_vals, pio_vals = [], []
    detail = []

    for code in codes:
        data = cache.get(code)
        if data is None:
            insufficient += 1
            continue
        # apply_trap_filters는 item["financials_data"] 안에서 재무제표를 읽는다
        # (info도 그 안에 있어야 함) - 최상위에 두면 전부 데이터부족으로 나온다.
        fd = {**data, "info": info_by.get(code, {})}
        item = {"financials_data": fd, "symbol": code, "market": "KR",
                "sector": (info_by.get(code, {}) or {}).get("sector", "")}
        try:
            r = apply_trap_filters(item)
        except Exception as e:
            insufficient += 1
            continue
        if r.get("status") == "insufficient_data":
            insufficient += 1
            continue
        total += 1
        if r["roe"] is not None:
            roe_vals.append(r["roe"])
        if r["piotroski"] is not None:
            pio_vals.append(r["piotroski"])
        if r["pass"]:
            passed += 1
            continue
        cats = sorted({_cat(f) for f in r["red_flags"]})
        for c in cats:
            flag_counter[c] += 1
        if len(cats) == 1:
            sole_reason[cats[0]] += 1
        detail.append((names.get(code, code), r["roe"], r["piotroski"], cats))

    print(f"=== 한국 유니버스 트랩 필터 분포 ===")
    print(f"판정 가능 {total}종목 / 통과 {passed} / 데이터부족 {insufficient}")
    print()
    print("탈락 사유별 종목 수(중복 포함):")
    for cat, n in flag_counter.most_common():
        print(f"  {cat}: {n}")
    print()
    print("이 기준 '하나만' 걸린 종목 수 (= 이것만 완화하면 통과):")
    for cat, n in sole_reason.most_common():
        print(f"  {cat}: {n}")
    print()

    def pctile(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        return s[min(int(len(s) * p / 100), len(s) - 1)]

    print(f"ROE 분포(%): 중앙값={pctile(roe_vals,50)} 25%={pctile(roe_vals,25)} "
          f"75%={pctile(roe_vals,75)} (n={len(roe_vals)})")
    print(f"  ROE >=12% 인 종목: {sum(1 for v in roe_vals if v >= 12)}개")
    print(f"  ROE >=8%  인 종목: {sum(1 for v in roe_vals if v >= 8)}개")
    print(f"  ROE >=10% 인 종목: {sum(1 for v in roe_vals if v >= 10)}개")
    print(f"Piotroski 분포: 중앙값={pctile(pio_vals,50)} (n={len(pio_vals)})")
    print(f"  F>=6 인 종목: {sum(1 for v in pio_vals if v >= 6)}개")
    print(f"  F>=5 인 종목: {sum(1 for v in pio_vals if v >= 5)}개")
    print()
    print("탈락 종목 상세(상위 25개):")
    for name, roe, pio, cats in detail[:25]:
        print(f"  {name}: ROE={roe} F={pio} 사유={','.join(cats)}")

    conn.close()


if __name__ == "__main__":
    main()
